"""Train a reproducible BERT role head with page-disjoint source and template tests."""
import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from kanji_translator.bert_context import LABELS, REVISION, VERSION, encode
from kanji_translator.request_contracts import canonical, digest

# Operator-authored teaching examples, not source quotations or expert annotations.
# The test uses different phrasings. Real-source results are reported separately.
TERMS = {
    'swordsmith_artisan': ['雲次', '正宗', '国光', '長義', '兼元', '兼定', '信国', '一文字助真'],
    'sword_school': ['一文字', '長船', '当麻', '来', '青江', '兼元', '信国', '粟田口', '法城寺', '保昌', '三原', '大原', '延寿', '千手院'],
    'sword_tradition': ['山城', '大和', '備前', '相州', '美濃'],
    'technical_sword_term': ['帽子', '反り', '地肌', '刃文', '板目肌', '直刃', '茎', '古刀'],
    'place_province': ['山城', '大和', '備前', '相州', '美濃', '大原', '長船', '久留米'],
    'era_date': ['慶長', '元禄', '永正', '天正', '寛文', '文政', '弘化', '正徳'],
    'measurement_dimension': ['二尺二寸七分', '一尺五寸', '三寸', '八分', '二尺', '五寸'],
    'family_clan': ['徳川', '藤原', '源', '平', '本阿弥', '細川'],
    'historical_person': ['徳川家康', '徳川吉宗', '織田信長', '豊臣秀吉', '徳川斉昭', '本阿弥光悦'],
    'ordinary_language': ['帽子', '反り', '雲', '一文字', '地肌', '次', '作品', '中心'],
    'unresolved': ['□□', '〓〓', '不明', '判読不能', '某', '一文字'],
}
TEMPLATES = {
    'swordsmith_artisan': [('刀工','が鍛えた太刀。'), ('刀鍛冶','の銘が刻まれる。'), ('作者は','という刀工である。'), ('名工','の作刀を調べる。'), ('刀工の名を','と読む。'), ('この刀を作った鍛冶は','である。'), ('この銘の作者である','本人の作品。'), ('刀匠','が打った刀身。')],
    'sword_school': [('刀工集団である','派の作風。'), ('流派の名は','である。'), ('','一派に属する刀工。'), ('','派に学んだ鍛冶の作品。'), ('刀工の流派として','の名を挙げる。'), ('一門の名は','、その門人が作る。'), ('','という刀工集団の系譜。'), ('','一門の諸工が鍛えた。')],
    'sword_tradition': [('五箇伝の一つ','伝に属する作風。'), ('刀剣の伝法である','伝の特徴。'), ('五ヶ伝では','伝に分類する。'), ('この鍛法は','伝の伝統を受け継ぐ。'), ('鍛刀の伝統は','伝である。'), ('五箇伝の分類で','伝と呼ぶ。'), ('作風の大きな伝統として','伝を挙げる。'), ('五伝のうち','伝の技法を継承する。')],
    'technical_sword_term': [('刀身の','を観察する。'), ('この刀の鑑定では','の特徴を見る。'), ('刀剣用語の','を説明する。'), ('刃の焼き入れによる','の状態。'), ('日本刀の','には特徴がある。'), ('太刀の','を鑑賞する。'), ('鍛えた刀身に現れる','を拡大する。'), ('刀の形状や鍛錬を示す','を調べた。')],
    'place_province': [('旧国名の','に住む。'), ('所在地は','国である。'), ('','という土地で鍛冶を営む。'), ('','の地名が銘に刻まれる。'), ('出身地は','である。'), ('','国住と銘する。'), ('地図に記された土地は','である。'), ('この刀工が住んだ場所は','であった。')],
    'era_date': [('年号は','である。'), ('','元年八月に作刀。'), ('年紀には','三年とある。'), ('','年間の出来である。'), ('元号の','を年紀に記す。'), ('','二年春の日付。'), ('製作年を示す年号は','と読める。'), ('制作年代は','五年に当たる。')],
    'measurement_dimension': [('刃長は','である。'), ('長さを測ると','になる。'), ('刀身の長さ','を記録。'), ('寸法は','と記される。'), ('幅は','である。'), ('長さ','の太刀。'), ('実測した刃渡りは','であった。'), ('寸尺の表記は','となっている。')],
    'family_clan': [('','家の家紋。'), ('一族の姓は','である。'), ('家系の名である','の一族。'), ('','氏の家系を調べる。'), ('姓として','を名乗った。'), ('氏族の','家に伝来する。'), ('家名だけが記される','の家系。'), ('この一族の名字は','である。')],
    'historical_person': [('歴史上の人物','が所持した。'), ('将軍','本人に献上した。'), ('人物名は','と記す。'), ('この人物は','という。'), ('','という人が命じた。'), ('大名の','の伝記。'), ('この歴史的人物の姓名は','である。'), ('記録に登場する人物','の生涯。')],
    'ordinary_language': [('頭にかぶる','を買った。'), ('日常語として','という言葉を使う。'), ('刀の用語ではなく普通の意味で','を使う。'), ('ここでは一般的な意味の','である。'), ('日常の文章にある','という語。'), ('普通の言葉としての','を説明する。'), ('この箇所の','は日常の表現である。'), ('刀剣に関係のない普通名詞の','という語。')],
    'unresolved': [('文字が潰れて','とは判読できない。'), ('文脈が欠けて','の意味は不明。'), ('読めない文字は','と仮に記した。'), ('','の判読は保留する。'), ('根拠がなく','の役割は未確定。'), ('','は文字も文脈も不明。'), ('不鮮明なため','を特定できない。'), ('資料不足により','の解釈は未解決。')],
}
ORDINARY_CONTEXTS = {
    '帽子':('頭にかぶる','を買った。'), '反り':('木の板の','を直した。'),
    '雲':('空に白い','が浮かぶ。'), '一文字':('紙に漢字を','だけ書いた。'),
    '地肌':('髪の間から','が見える。'), '次':('話の続きは','の頁にある。'),
    '作品':('画家の','を美術館で見た。'), '中心':('円の','を求める。'),
}


def split_page(page):
    value = int(hashlib.sha256(('bert-role-v1:' + page).encode()).hexdigest()[:8], 16) % 10
    return 'train' if value < 6 else 'validation' if value < 8 else 'test'


def freeze(references, predictions):
    """Use native line contexts containing the literal; never insert a missing OCR target."""
    refs = json.loads(Path(references).read_text())
    prediction_sha = digest(Path(predictions).read_bytes())
    predictions = {p['page_id']: p for p in map(json.loads, Path(predictions).read_text().splitlines())}
    rows, skipped = [], Counter()
    for page in refs['pages']:
        source = predictions[page['page_id']]
        nodes = [n for n in source['supporting']['document_groups']['nodes'] if n.get('literal_text')]
        used = set()
        for mention in page['mentions']:
            if mention.get('state') == 'disputed' or mention['category'] not in LABELS:
                skipped['disputed_or_unknown'] += 1
                continue
            target = mention['literal']
            box = mention.get('box')
            matches = []
            for node in nodes:
                text = node['literal_text']
                geometry = node.get('geometry')
                if not box or not geometry:
                    continue
                overlap = max(0, min(box[2], geometry[2])-max(box[0], geometry[0])) * max(0, min(box[3], geometry[3])-max(box[1], geometry[1]))
                if overlap <= 0:
                    continue
                start = 0
                while (a := text.find(target, start)) >= 0:
                    key = (node['id'], a, target)
                    if key not in used:
                        matches.append((overlap, key, text, a))
                    start = a+len(target)
            if not matches:
                skipped['literal_not_recovered_in_overlapping_native_line'] += 1
                continue
            _, key, text, a = max(matches, key=lambda v: v[0])
            used.add(key)
            rows.append({'id': mention['mention_id'], 'page_id': page['page_id'],
                         'source_sha256': page['source_sha256'], 'label': mention['category'],
                         'left': text[max(0, a-72):a], 'target': target, 'right': text[a+len(target):a+len(target)+72],
                         'origin': 'provisional_AI_source_annotation_with_native_OCR_context',
                         'split': split_page(page['page_id']), 'kind': 'source'})
    # Exact repeated contexts must not cross splits even when printed on separate pages.
    owners = defaultdict(set)
    for r in rows:
        owners[(r['left'], r['target'], r['right'])].add(r['split'])
    rows = [r for r in rows if len(owners[(r['left'], r['target'], r['right'])]) == 1]
    for label, terms in TERMS.items():
        for ti, (left, right) in enumerate(TEMPLATES[label]):
            split = 'train' if ti < 5 else 'validation' if ti == 5 else 'test'
            for target in terms:
                before,after=ORDINARY_CONTEXTS[target] if label=='ordinary_language' and ti==0 else (left,right)
                rows.append({'id': f'teaching:{label}:{ti}:{target}', 'label': label,
                             'left': before, 'target': target, 'right': after, 'split': split,
                             'kind': 'teaching', 'origin': 'operator_authored_synthetic_not_expert'})
    # Teaching heading grammar uses training-only fictional combinations. The
    # real source words and page labels are never copied into another split.
    for name in ('義光','則房','吉房','貞光','国行','包永','定宗','助光'):
        for school in TERMS['sword_school']:
            for suffix in ('', '〔鎌倉―備前〕', '一派', '一門'):
                left, right = '◇'+name, suffix
                rows.append({'id': 'heading-school:'+name+school+suffix, 'label': 'sword_school',
                             'left': left, 'target': school, 'right': right, 'split':'train',
                             'kind':'teaching','origin':'synthetic_heading_grammar_not_historical_identity'})
                rows.append({'id': 'heading-smith:'+name+school+suffix, 'label': 'swordsmith_artisan',
                             'left':'◇', 'target':name, 'right':school+suffix, 'split':'train',
                             'kind':'teaching','origin':'synthetic_heading_grammar_not_historical_identity'})
    return {'schema': 'bert-role-training-v1', 'rows': rows, 'skipped': dict(skipped),
            'reference_sha256': digest(Path(references).read_bytes()),
            'native_predictions_sha256': prediction_sha,
            'split_rule': 'SHA256(bert-role-v1:page_id) modulo 10: 0..5 train, 6..7 validation, 8..9 test; cross-split identical contexts removed',
            'human_expert_labels': 0}


def metrics(rows, predictions, mask):
    selected = [(r, p) for r, p in zip(rows, predictions) if mask(r)]
    counts = Counter((r['label'], LABELS[p]) for r, p in selected)
    return {'correct': sum(r['label'] == LABELS[p] for r, p in selected), 'total': len(selected),
            'accuracy': sum(r['label'] == LABELS[p] for r, p in selected)/len(selected) if selected else None,
            'by_category': {label: {'correct': counts[label, label], 'total': sum(n for (a, b), n in counts.items() if a == label)} for label in LABELS},
            'confusion': [{'reference': a, 'prediction': b, 'count': n} for (a, b), n in sorted(counts.items())]}


def validation_score(rows, predictions):
    values = []
    for kind in ('source', 'teaching'):
        result = metrics(rows, predictions, lambda r: r['split']=='validation' and r['kind']==kind)
        categories = [r['correct']/r['total'] for r in result['by_category'].values() if r['total']]
        if categories: values.append(sum(categories)/len(categories))
    return sum(values)/len(values)


def train(dataset, output, base, device):
    import torch
    torch.manual_seed(106)
    random.seed(106)
    output.mkdir(parents=True, exist_ok=True)
    rows = dataset['rows']
    feature_path = output/'features.pt'
    feature_key = digest(canonical({'rows': rows, 'revision': REVISION, 'encoder': VERSION}))
    if feature_path.exists() and (output/'features.sha256').read_text().strip() == feature_key:
        x = torch.load(feature_path, weights_only=True)
    else:
        x = encode(rows, {'bert_path': str(base), 'bert_device': device})
        torch.save(x, feature_path)
        (output/'features.sha256').write_text(feature_key)
    train_ids = [i for i, r in enumerate(rows) if r['split'] == 'train']
    val_ids = [i for i, r in enumerate(rows) if r['split'] == 'validation']
    mean = x[train_ids].mean(0)
    scale = x[train_ids].std(0).clamp_min(.1)
    x = (x-mean)/scale
    y = torch.tensor([LABELS.index(r['label']) for r in rows])
    torch.manual_seed(106)
    model = torch.nn.Linear(x.shape[1], len(LABELS))
    optimizer = torch.optim.AdamW(model.parameters(), lr=.003, weight_decay=.1)
    count = torch.bincount(y[train_ids], minlength=len(LABELS)).float().clamp_min(1)
    weight = (count.sum()/count).sqrt()
    # Synthetic and source validation both matter; no test observation selects a checkpoint.
    best_score, best, best_epoch = -1., None, 0
    for epoch in range(1, 301):
        model.train()
        optimizer.zero_grad()
        loss = torch.nn.functional.cross_entropy(model(x[train_ids]), y[train_ids], weight=weight)
        loss.backward()
        optimizer.step()
        if epoch % 10:
            continue
        model.eval()
        with torch.inference_mode():
            pred = model(x).argmax(-1).tolist()
            score = validation_score(rows, pred)
        if score > best_score:
            best_score, best_epoch = score, epoch
            best = {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best)
    with torch.inference_mode():
        probabilities = model(x).softmax(-1)
        predictions = probabilities.argmax(-1).tolist()
    head = {'version': VERSION, 'labels': list(LABELS), 'base_revision': REVISION,
            'mean': mean.tolist(), 'scale': scale.tolist(),
            'weight': best['weight'].tolist(), 'bias': best['bias'].tolist(),
            'threshold': .65, 'margin': .15, 'calibrated': False}
    raw = gzip.compress(canonical(head), mtime=0)
    (output/'bert_head.json.gz').write_bytes(raw)
    manifest = {'version': VERSION, 'sha256': digest(raw), 'base_revision': REVISION,
                'training_dataset_sha256': digest(canonical(dataset)), 'encoder_frozen': True,
                'feature_width': x.shape[1], 'best_validation_epoch': best_epoch,
                'seed': 106, 'torch': torch.__version__}
    (output/'bert_head_manifest.json').write_bytes(canonical(manifest)+b'\n')
    report = {'schema': 'bert-role-evaluation-v1', 'manifest': manifest,
              'counts': dict(Counter(r['split']+':'+r['kind'] for r in rows)),
              'metrics': {split+':'+kind: metrics(rows, predictions, lambda r, s=split, k=kind: r['split']==s and r['kind']==k) for split in ('train', 'validation', 'test') for kind in ('source', 'teaching')},
              'limitations': ['Source labels are provisional AI annotations, not expert truth.', 'Source role accuracy is conditional on exact target recovery and matching geometry, not end-to-end OCR accuracy.', 'No source tradition labels exist in this cohort; tradition behavior has synthetic tests only.', 'The pretrained BERT encoder is frozen; the linear role head is trained.', 'Softmax scores are not calibrated correctness probabilities.', 'Earlier test observations informed development; these frozen pages are regression evidence, not a fresh blind test.']}
    (output/'report.json').write_bytes(canonical(report)+b'\n')
    (output/'decisions.json').write_bytes(canonical([{'id': r['id'], 'split': r['split'], 'kind': r['kind'], 'reference': r['label'], 'prediction': LABELS[p], 'probabilities': probs} for r, p, probs in zip(rows, predictions, probabilities.tolist())])+b'\n')
    print(json.dumps({'counts': report['counts'], 'test': {k: v for k, v in report['metrics'].items() if k.startswith('test:')}, 'best_validation_epoch': best_epoch}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--references', type=Path)
    p.add_argument('--predictions', type=Path)
    p.add_argument('--dataset', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--base', type=Path, required=True)
    p.add_argument('--device', default='cpu')
    args = p.parse_args()
    dataset = json.loads(gzip.decompress(args.dataset.read_bytes()) if args.dataset.suffix=='.gz' else args.dataset.read_bytes()) if args.dataset else freeze(args.references, args.predictions)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output/'dataset.json').write_bytes(canonical(dataset)+b'\n')
    train(dataset, args.output, args.base, args.device)


if __name__ == '__main__':
    main()
