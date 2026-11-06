"""Frozen Japanese BERT features and a trained, evidence-constrained role head."""
import gzip
import json
import os
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

from .data_paths import data_dir
from .request_contracts import digest

VERSION = 'japanese-bert-span-context-v1'
MODEL_ID = 'tohoku-nlp/bert-base-japanese-char-v3'
REVISION = 'ccddee593a9e03a589ae1feedcd4d1eb06d6ba02'
LABELS = ('technical_sword_term', 'swordsmith_artisan', 'sword_school',
          'sword_tradition', 'measurement_dimension', 'historical_person',
          'family_clan', 'place_province', 'era_date', 'ordinary_language', 'unresolved')


def base_path(config=None):
    return Path((config or {}).get('bert_path') or os.environ.get('KOSHIRAI_BERT_DIR') or data_dir() / 'bert')


@lru_cache(maxsize=2)
def encoder(path, device):
    """Load local, hash-verified weights. Inference never downloads or executes remote code."""
    import torch
    from transformers import BertJapaneseTokenizer, BertModel
    path = Path(path)
    if not (path/'koshirai_base.json').is_file():
        raise RuntimeError('BERT is not installed. Install the bert package extra and run python -m kanji_translator.install_bert')
    pin = json.loads((path / 'koshirai_base.json').read_text())
    manifest = json.loads(files('kanji_translator').joinpath('resources/bert_base_manifest.json').read_text())
    if pin != manifest or pin['revision'] != REVISION or pin['model_id'] != MODEL_ID:
        raise ValueError('BERT base manifest differs from the pinned release')
    for name, sha in pin['files'].items():
        if digest((path / name).read_bytes()) != sha:
            raise ValueError('BERT base file hash mismatch: ' + name)
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    tokenizer = BertJapaneseTokenizer.from_pretrained(str(path), local_files_only=True)
    model = BertModel.from_pretrained(str(path), local_files_only=True).to(device).eval()
    model.requires_grad_(False)
    return tokenizer, model, pin


def examples(text, spans):
    """Bound context around exact source offsets; never replace a source character."""
    return [{'left': text[max(0, a-72):a], 'target': text[a:b], 'right': text[b:b+72]} for a, b in spans]


def tensor_batch(items, tokenizer, device):
    import torch
    sequences, bounds = [], []
    for item in items:
        left = tokenizer.encode(item['left'], add_special_tokens=False)[-72:]
        target = tokenizer.encode(item['target'], add_special_tokens=False)[:48]
        right = tokenizer.encode(item['right'], add_special_tokens=False)[:72]
        if not target:
            raise ValueError('BERT target must contain at least one token')
        ids = [tokenizer.cls_token_id] + left + [tokenizer.sep_token_id]
        a = len(ids)
        ids += target
        b = len(ids)
        ids += [tokenizer.sep_token_id] + right + [tokenizer.sep_token_id]
        sequences.append(ids)
        bounds.append((a, b))
    width = max(map(len, sequences))
    ids = torch.tensor([s + [tokenizer.pad_token_id]*(width-len(s)) for s in sequences], device=device)
    attention = torch.tensor([[1]*len(s)+[0]*(width-len(s)) for s in sequences], device=device)
    return ids, attention, bounds, list(map(len, sequences))


def pooled(hidden, bounds, lengths):
    import torch
    result = []
    for i, ((a, b), length) in enumerate(zip(bounds, lengths)):
        positions = list(range(1, a-1)) + list(range(b+1, length-1))
        context = hidden[i, positions].mean(0) if positions else hidden[i, 0]
        result.append(torch.cat((hidden[i, 0], hidden[i, a:b].mean(0), context)))
    return torch.stack(result)


def encode(items, config=None):
    """Return CLS, target-mean and surrounding-context-mean contextual vectors."""
    import torch
    config = config or {}
    device = config.get('bert_device', 'cpu')
    tokenizer, model, _ = encoder(str(base_path(config).resolve()), device)
    output = []
    for offset in range(0, len(items), 24):
        chunk = items[offset:offset+24]
        ids, attention, bounds, lengths = tensor_batch(chunk, tokenizer, device)
        with torch.inference_mode():
            hidden = model(input_ids=ids, attention_mask=attention).last_hidden_state
            output.extend(pooled(hidden, bounds, lengths).cpu().unbind())
    return torch.stack(output) if output else torch.empty((0, 2304))


@lru_cache(maxsize=1)
def head():
    root = files('kanji_translator').joinpath('resources')
    raw = root.joinpath('bert_head.json.gz').read_bytes()
    manifest = json.loads(root.joinpath('bert_head_manifest.json').read_text())
    if digest(raw) != manifest['sha256']:
        raise ValueError('BERT head hash mismatch')
    value = json.loads(gzip.decompress(raw))
    if value['version'] != VERSION or value['labels'] != list(LABELS):
        raise ValueError('BERT head schema mismatch')
    if value['base_revision'] != REVISION:
        raise ValueError('BERT head uses a different encoder')
    return value, manifest


def classify(items, config=None):
    import torch
    values, manifest = head()
    features = encode(items, config)
    standardized = (features - torch.tensor(values['mean'])) / torch.tensor(values['scale'])
    with torch.inference_mode():
        logits = standardized @ torch.tensor(values['weight']).T + torch.tensor(values['bias'])
        probabilities = logits.softmax(-1).tolist()
    results = []
    for row in probabilities:
        order = sorted(range(len(row)), key=lambda i: -row[i])
        results.append({'category': LABELS[order[0]], 'model_probability': row[order[0]],
                        'margin': row[order[0]] - row[order[1]],
                        'probabilities': dict(zip(LABELS, row)), 'calibrated': False,
                        'version': VERSION, 'head_sha256': manifest['sha256'],
                        'base_revision': REVISION})
    return results


def rerank(ranked, decision):
    """Choose an existing supported role, or abstain. Never invent a meaning or identity."""
    values, _ = head()
    reliable = (decision['model_probability'] >= values['threshold']
                and decision['margin'] >= values['margin'])
    category = decision['category']
    supported = [r for r in ranked if r['category'] == category and r.get('support') and
                 (r['score'] >= 1. or (r.get('source') in ('jmdict','jmnedict') and
                  category in ('ordinary_language','historical_person','family_clan')))]
    state = 'context_selected' if reliable and supported and category != 'unresolved' else 'requires_review'
    if state == 'context_selected':
        chosen = supported[0]
        if chosen['score'] < 1.:
            chosen = {**chosen, 'score':3., 'selection_evidence':chosen.get('selection_evidence',[])+['bert_context_supported_dictionary_role']}
        ranked = [chosen] + [r for r in ranked if r is not supported[0]]
    # A distribution is model output, not evidence that the meaning is true.
    return ranked, {**decision, 'state': state,
                    'reason': 'supported_context_role' if state == 'context_selected' else
                              'unsupported_context_role' if reliable and not supported else 'uncertain_context_role'}
