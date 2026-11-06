"""Pure saved-DOM Club parsing; acquisition remains with scrapers."""
import re
from urllib.parse import urljoin,urlsplit
from bs4 import BeautifulSoup

SWORD_RE = re.compile(r"^/swords/([A-Za-z0-9][A-Za-z0-9_-]*)$")


VIEW_RE = re.compile(r"^/view/(school|smith)/swords/(\d+)$")


CATALOGUE_RE = re.compile(r"^/swords(?:/(list|kyoho-meibutsu-cho))?$")


RECORD_PAGE_JS = r"""(()=>{const content=document.querySelector('td.node-mc .content')||document.querySelector('#content')||document.body;
 const rows=[...content.querySelectorAll('tr')].map(tr=>[...tr.querySelectorAll('th,td')].map(x=>(x.innerText||'').trim())).filter(x=>x.length);
 const fields={};for(const tr of content.querySelectorAll('tr')){const cells=[...tr.querySelectorAll('th,td')];if(cells.length===2){const k=(cells[0].innerText||'').trim(),v=(cells[1].innerText||'').trim();if(k&&v&&!fields[k])fields[k]=v;}}
 return JSON.stringify({url:location.href,title:document.title,text:(content.innerText||'').trim(),html:content.outerHTML,
  heading:(document.querySelector('h2.title')||document.querySelector('h1')||{}).innerText||'',
  submitted:(document.querySelector('.submitted')||{}).innerText||'',fields,rows,
  links:[...document.querySelectorAll('a[href]')].map(a=>a.href).filter(Boolean),
  images:[...document.querySelectorAll('img')].map(img=>{const a=img.closest('a[href]');return {url:img.currentSrc||img.src,
   linked_original_url:a?a.href:'',alt:img.alt||'',width:img.naturalWidth||0,height:img.naturalHeight||0}}).filter(x=>x.url)})})()"""


def parse_record_html(document_html: str, source_url: str) -> dict:
    """Replay every labelled sword-table cell from saved source HTML.

    The source uses two label/value pairs per row and occasional colspan values;
    positional two-cell heuristics lose those measurements.  Occurrences retain
    literal blanks and repeats. ``fields`` remains a compatibility first
    nonblank value map and is never used to overwrite source evidence.
    """
    soup = BeautifulSoup(document_html or "", "html.parser")
    content = soup.select_one("td.node-mc .content") or soup.select_one("#content") or soup.body or soup
    fields, occurrences, headings = {}, [], []
    semantic_tables = [table for table in content.find_all("table") if table.select_one(".smith-field-name")]
    for table_index, table in enumerate(semantic_tables):
        prior = table.find_previous(["h2", "h3"])
        section = prior.get_text(" ", strip=True) if prior and prior in content.descendants else ""
        for row_index, tr in enumerate(table.find_all("tr")):
            cells = tr.find_all(["th", "td"], recursive=False)
            for cell_index, label_cell in enumerate(cells):
                if "smith-field-name" not in (label_cell.get("class") or []):
                    continue
                label = label_cell.get_text(" ", strip=True)
                if not label:
                    continue
                value_cell = next((candidate for candidate in cells[cell_index + 1:]
                                   if "smith-field-value" in (candidate.get("class") or [])), None)
                if value_cell is None:
                    continue
                label_links = [urljoin(source_url, anchor["href"]) for anchor in label_cell.select("a[href]")]
                value = value_cell.get_text(" ", strip=True)
                occurrence = {
                    "label": label, "value": value, "label_html": "".join(str(child) for child in label_cell.contents),
                    "label_links": label_links, "value_html": "".join(str(child) for child in value_cell.contents),
                    "value_links": [urljoin(source_url, anchor["href"]) for anchor in value_cell.select("a[href]")],
                    "section_heading_raw": section,
                    "locator": f"#source-content/table={table_index}/row={row_index}/label-cell={cell_index}",
                }
                occurrences.append(occurrence)
                if value and label not in fields:
                    fields[label] = value
    for heading_index, heading in enumerate(content.find_all(["h2", "h3"])):
        text = heading.get_text(" ", strip=True)
        if text:
            headings.append({"heading_level": heading.name, "heading_raw": text,
                             "heading_html": "".join(str(child) for child in heading.contents),
                             "links": [urljoin(source_url, anchor["href"]) for anchor in heading.select("a[href]")],
                             "locator": f"#source-content/heading={heading_index}"})
    outbound = []
    # Preserve source URLs in literal References and Links fields. Citations
    # remain assertions about this record and neither type becomes a sword
    # identity claim or an unbounded crawl queue.
    for occurrence in occurrences:
        label = occurrence["label"].strip().casefold()
        if label != "links" and not label.startswith("references"):
            continue
        relation_kind = "citation" if label.startswith("references") else "external_link"
        value = BeautifulSoup(occurrence["value_html"], "html.parser")
        for anchor_index, anchor in enumerate(value.select("a[href]")):
            outbound.append({
                "field_label_raw": occurrence["label"],
                "relation_kind": relation_kind,
                "anchor_text": anchor.get_text(" ", strip=True),
                "anchor_html": str(anchor),
                "destination_url": urljoin(source_url, anchor["href"]),
                "locator": occurrence["locator"] + f"/value-link={anchor_index}",
            })
    return {"fields": fields, "field_occurrences": occurrences,
            "section_headings": headings, "outbound_source_links": outbound}


def enrich_record_data(data: dict, observation: dict, source_url: str) -> dict:
    """Make live capture use the same replayable parser as offline evidence."""
    parsed = parse_record_html(observation.get("html") or data.get("html") or "", source_url)
    return {**data, **parsed}


def parse_catalogue_html(document_html: str, source_url: str) -> dict:
    """Replay only the catalogue's views table, including literal blank cells."""
    soup = BeautifulSoup(document_html or "", "html.parser")
    table = soup.select_one(".views-table")
    if table is None:
        return {"catalogue_headers_raw": [], "catalogue_rows_raw": []}
    header_row = table.find("tr")
    headers = [cell.get_text(" ", strip=True) for cell in header_row.find_all(["th", "td"], recursive=False)] if header_row else []
    rows = []
    for tr in table.select("tbody tr"):
        cells = tr.find_all(["th", "td"], recursive=False)
        if not cells:
            continue
        record_url = ""
        for anchor in tr.select("a[href]"):
            found = exact_url(urljoin(source_url, anchor["href"]), SWORD_RE)
            if found:
                record_url = found[0]
                break
        # Drupal places the column-heading row inside tbody on these pages.
        if not record_url:
            continue
        rows.append({"cells_raw": [cell.get_text(" ", strip=True) for cell in cells],
                     "record_url": record_url})
    return {"catalogue_headers_raw": headers, "catalogue_rows_raw": rows}


def exact_url(value: str, pattern: re.Pattern[str]) -> tuple[str, re.Match[str]] | None:
    parsed = urlsplit(value)
    if parsed.hostname not in {"nihontoclub.com", "www.nihontoclub.com"}:
        return None
    path = parsed.path.rstrip("/")
    match = pattern.fullmatch(path)
    if not match:
        return None
    query = parsed.query if re.fullmatch(r"page=\d+", parsed.query) else ""
    return "https://nihontoclub.com" + path + (("?" + query) if query else ""), match


def exact_catalogue_url(value: str) -> str | None:
    parsed = urlsplit(value)
    if parsed.hostname not in {"nihontoclub.com", "www.nihontoclub.com"} or not CATALOGUE_RE.fullmatch(parsed.path.rstrip("/")):
        return None
    # The verified public pager is the sole ``page=<digits>`` query.  The same
    # table also emits sort/filter controls, which must not become crawl seeds.
    if parsed.query and not re.fullmatch(r"page=\d+", parsed.query):
        return None
    return "https://nihontoclub.com" + parsed.path.rstrip("/") + (("?" + parsed.query) if parsed.query else "")


def catalogue_links(links: list[str], catalogue_url: str) -> tuple[set[str], set[str]]:
    swords, pagers = set(), set()
    catalogue_path = urlsplit(catalogue_url).path.rstrip("/")
    for link in links:
        catalogue = exact_catalogue_url(link)
        if catalogue and urlsplit(catalogue).path.rstrip("/") == catalogue_path and catalogue != catalogue_url:
            pagers.add(catalogue); continue
        found = exact_url(link, SWORD_RE)
        if found and not CATALOGUE_RE.fullmatch(urlsplit(found[0]).path):
            swords.add(found[0])
    return swords, pagers


SMITH_PAGE_JS=r"""(()=>{const content=document.querySelector('td.node-mc .content')||document.querySelector('#content')||document.body;
 const rows=[...content.querySelectorAll('tr')].map(tr=>({cells:[...tr.querySelectorAll('th,td')].map(x=>(x.innerText||'').trim()),
   smith_url:(tr.querySelector('a[href^="/smiths/"]')||{}).href||''}));
 const fields={},field_occurrences=[],primary_field_conflicts=[];
 [...content.querySelectorAll('tr')].forEach((tr,row_index)=>{const k=tr.querySelector('.smith-field-name');if(!k)return;const label=(k.innerText||'').trim();if(!label)return;
   [...tr.querySelectorAll('.smith-field-value')].forEach((v,value_index)=>{const value=(v.innerText||'').trim(),locator=`content tr:nth-of-type(${row_index+1}) .smith-field-value:nth-of-type(${value_index+1})`;
     field_occurrences.push({label,value,locator});if(!(label in fields))fields[label]=value;
     // ID is the producer's only admission-critical labelled primary field.
     if(label==='ID'&&fields[label]!==value&&!primary_field_conflicts.some(x=>x.label===label&&x.value===value))primary_field_conflicts.push({label,value,locator,first_value:fields[label]});
   });});
 const ratings=[...content.querySelectorAll('.smith-rating-table tr')].map(tr=>[...tr.querySelectorAll('th,td')].map(x=>(x.innerText||'').trim())).filter(x=>x.length);
 return JSON.stringify({url:location.href,title:document.title,text:(content.innerText||'').trim(),html:content.outerHTML,
  heading:(document.querySelector('h2.title')||document.querySelector('h1')||{}).innerText||'',
  submitted:(document.querySelector('.submitted')||{}).innerText||'',kanji_name:(content.querySelector('.kanji-name td')||{}).innerText||'',
  kanji_details:(content.querySelector('.smith-kanji-details')||{}).innerText||'',fields,field_occurrences,primary_field_conflicts,ratings,rows,
  links:[...document.querySelectorAll('a[href]')].map(a=>a.href).filter(Boolean),
  images:[...document.querySelectorAll('img')].map(img=>img.currentSrc||img.src).filter(Boolean)})})()"""


def _bibliography_url(href:str,base:str,reference_context:bool)->str:
    parsed=urlsplit(urljoin(base,href)); path=parsed.path.rstrip("/")
    if parsed.netloc not in ("nihontoclub.com","www.nihontoclub.com") or not reference_context:return ""
    if not (re.fullmatch(r"/(?:biblio|bibliography)(?:/[^/]+)*",path) or re.fullmatch(r"/node/\d+",path)):return ""
    return "https://nihontoclub.com"+path+("?"+parsed.query if parsed.query else "")


def _reference_urls(html:str,base:str)->set[str]:
    soup=BeautifulSoup(html,"html.parser"); found=set()
    for container in soup.select(".references, .biblio, .biblio-entry"):
      for link in container.select("a[href]"):
        if url:=_bibliography_url(link["href"],base,True):found.add(url)
    return found


def extract_comments(document_html:str,source_url:str)->list[dict]:
    """Extract only Drupal's primary #comments block, never sidebar/nav text."""
    comments=[]; root=BeautifulSoup(document_html,"html.parser").select_one("#comments")
    if not root:return comments
    for table in root.select("table.comment"):
      anchor=table.find_previous("a",id=re.compile(r"^comment-\d+$")); submitted=table.select_one(".submitted");title=table.select_one("h3.title");body=table.select_one("td#comment-mc > .content")
      if not anchor or not submitted or not body:continue
      links=[urljoin(source_url,a["href"]) for a in body.select("a[href]")]
      reply=table.select_one(".comment_reply a[href]")
      comments.append({"comment_anchor_id":anchor["id"],"submitted_raw":submitted.get_text(" ",strip=True),
        "author_raw":re.sub(r"^.*?Submitted by\s+(.+?)\s+on\s+.*$",r"\1",submitted.get_text(" ",strip=True)),
        "date_raw":re.sub(r"^.*?\s+on\s+(.+?)\.?$",r"\1",submitted.get_text(" ",strip=True)),
        "title_raw":title.get_text(" ",strip=True) if title else "","body_html":str(body),"body_text":body.get_text(" ",strip=True),
        "links":links,"reply_url":urljoin(source_url,reply["href"]) if reply else ""})
    return comments


def _comment_pager_urls(html:str,base:str)->set[str]:
    """Return only same-smith Drupal comment pages, never global/navigation pagers."""
    origin=urlsplit(base);found=set();root=BeautifulSoup(html,"html.parser").select_one("#comments")
    if not root:return found
    for link in root.select(".pager a[href]"):
      candidate=urlsplit(urljoin(base,link["href"]))
      if (candidate.scheme,candidate.netloc,candidate.path)==(origin.scheme,origin.netloc,origin.path) and re.fullmatch(r"page=\d+",candidate.query):
        found.add(candidate._replace(fragment="").geturl())
    return found


def _pager_urls(html:str,base:str)->set[str]:
    current=urlsplit(base);found=set()
    for link in BeautifulSoup(html,"html.parser").select(".pager a[href], .item-list .pager a[href]"):
      candidate=urlsplit(urljoin(base,link["href"]))
      if candidate.netloc in ("nihontoclub.com","www.nihontoclub.com") and candidate.path==current.path and re.fullmatch(r"page=\d+",candidate.query):
        found.add("https://nihontoclub.com"+candidate.path+"?"+candidate.query)
    return found


def parse_smith_html(document_html, source_url=""):
    soup=BeautifulSoup(document_html or "", "html.parser")
    content=soup.select_one("td.node-mc .content") or soup.select_one("#content") or soup.body or soup
    fields={};occurrences=[]
    for index,tr in enumerate(content.select("tr")):
        cells=tr.find_all(["th","td"],recursive=False)
        if len(cells)==2:
            label,value=(c.get_text(" ",strip=True) for c in cells)
            occurrences.append({"label":label,"value":value,"locator":f"table-row:{index}"})
            if label and value:fields.setdefault(label,value)
    return {"fields":fields,"field_occurrences":occurrences,"text":content.get_text(" ",strip=True),"comments":extract_comments(document_html,source_url)}
