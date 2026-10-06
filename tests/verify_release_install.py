"""Execute an installed skill outside the source checkout, with synthetic data."""
import json
import os
import re
import subprocess
import base64
import sys
from pathlib import Path
from datetime import datetime,timezone,timedelta


def main():
    installed=Path(sys.argv[1]).resolve()
    root=Path(sys.argv[2]).resolve();root.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ);env.pop('PYTHONPATH',None);env['WEREAD_API_KEY']=''
    subprocess.run([sys.executable,'-X','utf8',str(installed/'scripts/skill_release.py')],cwd=root,env=env,check=True)
    for count in (0,1,15):
        case=root/str(count);case.mkdir(exist_ok=True)
        stamp=int(datetime(2026,6,1,tzinfo=timezone(timedelta(hours=8))).timestamp())
        books=[{'bookId':str(i),'title':f'合成书目{i+1}','author':'示例作者'} for i in range(count)]
        snapshot={'year':2026,'as_of':'2026-10-06','shelf':{'books':books},'annual':{'readStat':[{'stat':'读过','counts':f'{count}本'}],'readLongest':[{'book':b,'readTime':120} for b in books[:10]]},
            'non_ranked_progress':[{'book_id':b['bookId'],'title':b['title'],'last_read':'2026-06-01','is_started':True,'progress':1} for b in books[10:]]}
        materials={'year':2026,'books':[{'book_id':b['bookId'],'title':b['title'],'notes_scope':'all_time','collection':{'highlights':'complete','thoughts':'complete'},'highlights':[],'thoughts':[],'errors':[]} for b in books]}
        cover=case/'synthetic-cover.png';cover.write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAFElEQVR4nGP8/ukpAwMDEwMYQCkANbAC1LhAEWwAAAAASUVORK5CYII='))
        covers={b['bookId']:str(cover) for b in books}
        for name,value in [('snapshot',snapshot),('materials',materials),('covers',covers)]:
            (case/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        command=[sys.executable,'-X','utf8',str(installed/'scripts/generate_reading_html.py'),'--year','2026','--output',str(case/'index.html'),
            '--annual-snapshot',str(case/'snapshot.json'),'--materials',str(case/'materials.json'),'--covers',str(case/'covers.json')]
        result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,encoding='utf-8',check=True)
        status=json.loads(result.stdout.strip());assert status['status']=='complete',status
        html=(case/'index.html').read_text('utf-8')
        payload=json.loads(re.search(r'<script id="reading-data"[^>]*>(.*?)</script>',html,re.S).group(1))
        assert len(payload['books'])==count and all(b['cover'].startswith('data:image/') for b in payload['books'])
        assert 'data:font/woff2;base64,' not in html
        assert 'ReadingInsights' not in html and 'PolyForm Noncommercial' in html
        expected_css=(installed/'assets/reading-app.css').read_text('utf-8')+'\n'+(installed/'assets/reading-art.css').read_text('utf-8')
        assert re.search(r'<style>(.*?)</style>',html,re.S).group(1).strip()==expected_css.strip()
        assert 'display-reading' in html and 'hero-art' in html and 'bookShareTrigger' in html
        print(json.dumps({'count':count,'status':'pass','bytes':status['bytes']},ensure_ascii=False))


if __name__=='__main__':main()
