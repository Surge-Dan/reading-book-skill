"""Read-only citation/coverage acceptance against an actual supplied ebook."""
import hashlib
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'
sys.path.insert(0, str(SCRIPTS))
from ebook_document import parse_document, build_chunks


def main():
    source, output = map(Path, sys.argv[1:3])
    document = parse_document(source)
    analysis = json.loads((output / 'analysis.json').read_text('utf-8'))
    audit = json.loads((output / 'validation-report.json').read_text('utf-8'))
    elements = {element['element_id']: element for element in document['elements']}
    assert analysis['source_hash'] == hashlib.sha256(source.read_bytes()).hexdigest()
    coverage = analysis['coverage']
    assert coverage['chunks_total'] == coverage['chunks_processed'] == len(build_chunks(document))
    citations = []
    for category in ('themes', 'methods', 'cases', 'counterexamples', 'glossary', 'references'):
        for item in analysis.get(category, []):
            for citation in item.get('sources', []):
                element = elements.get(citation['element_id'])
                assert element and citation['quote'] in element['text'], 'Citation not in source element'
                assert citation['location'] == element['location'], 'Citation location mismatch'
                citations.append(citation)
    assert citations, 'Actual-book result contains no source citations'
    assert (output / 'DIGEST.md').is_file() and (output / 'index.html').is_file()
    print(json.dumps({'source_hash': 'match', 'body_elements': len(elements),
                      'citations_checked': len(citations), 'full_chunk_coverage': 'pass',
                      'quality_status': analysis['quality_status'],
                      'warnings': coverage.get('warnings', []),
                      'validation_report_present': bool(audit)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
