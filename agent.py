import json, os, re, time
from pathlib import Path
from urllib.parse import urljoin
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')

OLLAMA_URL = os.getenv('OLLAMA_URL','http://127.0.0.1:11434').rstrip('/')
MODEL = os.getenv('OLLAMA_MODEL','qwen2.5-coder:7b')
ERP_URL = os.getenv('ERPNEXT_URL','https://stage2-salma.altersense.net').rstrip('/')
USER = (os.getenv('ERPNEXT_USER') or os.getenv('ERPNEXT_USERNAME') or os.getenv('ERPNext_USER') or '').strip()
PASSWORD = (os.getenv('ERPNEXT_PASSWORD') or os.getenv('ERP_PASSWORD') or os.getenv('ERPNext_PASSWORD') or '').strip()
HEADLESS = os.getenv('HEADLESS','false').lower() == 'true'
SLOW_MO = int(os.getenv('SLOW_MO','80'))
MAX_STEPS = int(os.getenv('MAX_STEPS','40'))
TIMEOUT = int(os.getenv('ACTION_TIMEOUT','15000'))

ART = ROOT/'artifacts'; SHOTS = ART/'screenshots'; ART.mkdir(exist_ok=True); SHOTS.mkdir(exist_ok=True)
LOG = ART/'execution.log'; REPORT = ART/'test-results.json'

def log(s):
    line=f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {s}"
    print(line, flush=True)
    with LOG.open('a',encoding='utf-8') as f: f.write(line+'\n')

def ask_qwen(messages):
    r=requests.post(f'{OLLAMA_URL}/api/chat',json={'model':MODEL,'messages':messages,'stream':False,'format':'json','options':{'temperature':0}},timeout=120)
    r.raise_for_status(); return r.json()['message']['content']

def parse_action(raw):
    raw=raw.strip(); raw=re.sub(r'```(?:json)?','',raw,flags=re.I).replace('```','').strip()
    try: data=json.loads(raw)
    except json.JSONDecodeError:
        a,b=raw.find('{'),raw.rfind('}')
        if a<0 or b<0: raise ValueError('Qwen did not return JSON: '+raw)
        data=json.loads(raw[a:b+1])
    if not isinstance(data,dict) or not data.get('action'): raise ValueError('Invalid Qwen action: '+raw)
    return data

def logged_in(page):
    if '/app' in page.url.lower() or '/desk' in page.url.lower(): return True
    try:
        t=page.locator('body').inner_text(timeout=1500).lower()
        return sum(x in t for x in ['search or type a command','workspace','accounting','inventory','home']) >= 2
    except: return False

def visible(page, selectors):
    for s in selectors:
        try:
            loc=page.locator(s)
            for i in range(loc.count()):
                e=loc.nth(i)
                if e.is_visible() and e.is_enabled(): return e
        except: pass
    return None

def login(page):
    if logged_in(page): log('Already logged in.'); return
    if not USER or not PASSWORD: raise RuntimeError('ERPNext credentials missing in .env')
    u=visible(page,["input[name='usr']","input[name='login']","input[autocomplete='username']","input[type='email']"])
    p=visible(page,["input[name='pwd']","input[name='password']","input[type='password']"])
    if not u or not p: raise RuntimeError('Visible login fields not found')
    u.fill(USER); p.fill(PASSWORD); log('Credentials filled locally.')
    b=visible(page,["button[type='submit']","button:has-text('Login')","button:has-text('Log In')","input[type='submit']"])
    if not b: raise RuntimeError('Login button not found')
    b.click()
    for i in range(30):
        page.wait_for_timeout(500)
        if logged_in(page): log(f'LOGIN SUCCESS: {page.url}'); return
    try: page.screenshot(path=str(SHOTS/'login_failure.png'),full_page=True)
    except: pass
    raise RuntimeError(f'Login failed: {page.url}')

def snapshot(page):
    try: body=page.locator('body').inner_text(timeout=4000)[:10000]
    except: body=''
    items=[]
    sels=["input:visible","textarea:visible","select:visible","button:visible","a:visible","[role='button']:visible","[role='option']:visible","[role='menuitem']:visible"]
    for s in sels:
        try:
            loc=page.locator(s)
            for i in range(min(loc.count(),60)):
                e=loc.nth(i)
                try:
                    items.append({'tag':e.evaluate('(x)=>x.tagName.toLowerCase()'),'text':(e.inner_text(timeout=300) or '')[:100],'placeholder':e.get_attribute('placeholder') or '','aria':e.get_attribute('aria-label') or '','name':e.get_attribute('name') or '','type':e.get_attribute('type') or '','href':e.get_attribute('href') or ''})
                except: pass
        except: pass
    return f"URL: {page.url}\nTITLE: {page.title()}\nPAGE TEXT:\n{body}\n\nVISIBLE CONTROLS:\n{json.dumps(items[:220],ensure_ascii=False)}"

def search(page,q):
    q=str(q or '').strip()
    if not q: return 'SEARCH_FAILED: empty query'
    sels=["input[placeholder*='Search or type a command']","input[placeholder*='Search or type']","input[aria-label*='Search']","input[aria-label*='search']","input[type='search']"]
    box=visible(page,sels)
    if not box:
        try: page.keyboard.press('Control+K'); page.wait_for_timeout(500)
        except: pass
        box=visible(page,sels)
    if not box: return 'SEARCH_INPUT_NOT_FOUND'
    box.click(); box.fill(q); page.wait_for_timeout(1500)
    return f'SEARCH_SUCCESS: {q}'

def click_text(page,text):
    text=str(text or '').strip()
    for loc in [page.get_by_role('button',name=text,exact=True),page.get_by_role('link',name=text,exact=True),page.get_by_text(text,exact=True),page.get_by_text(text,exact=False)]:
        try:
            for i in range(loc.count()):
                e=loc.nth(i)
                if e.is_visible() and e.is_enabled(): e.click(timeout=TIMEOUT); return f'CLICK_TEXT_SUCCESS: {text}'
        except: pass
    return f'CLICK_TEXT_FAILED: {text}'

def execute(page,a):
    name=a.get('action','').lower()
    if name=='login': login(page); return 'LOGIN_SUCCESS'
    if name=='read_page': return snapshot(page)
    if name=='search': return search(page,a.get('query') or a.get('text') or a.get('target'))
    if name=='wait': page.wait_for_timeout(max(100,min(int(a.get('ms',1000)),10000))); return 'WAIT_SUCCESS'
    if name=='screenshot':
        n=re.sub(r'[^A-Za-z0-9_.-]','_',a.get('name','step')); p=SHOTS/f'{n}.png'; page.screenshot(path=str(p),full_page=True); return f'SCREENSHOT_SUCCESS: {p}'
    if name=='done': return '__DONE__'+str(a.get('result','Task completed.'))
    if name=='goto':
        u=str(a.get('url','')).strip()
        u=urljoin(ERP_URL+'/',u) if not re.match(r'^https?://',u,re.I) else u
        if not u.startswith(ERP_URL): return 'GOTO_BLOCKED: outside ERPNext domain'
        page.goto(u,wait_until='domcontentloaded',timeout=30000); page.wait_for_timeout(500); return f'GOTO_SUCCESS: {page.url}'
    if name in ('click_text','click_by_text'): return click_text(page,a.get('text') or a.get('target'))
    if name=='click':
        s=str(a.get('selector','')).strip(); loc=page.locator(s)
        for i in range(loc.count()):
            try:
                e=loc.nth(i)
                if e.is_visible() and e.is_enabled(): e.click(timeout=TIMEOUT); return f'CLICK_SUCCESS: {s}'
            except: pass
        return f'CLICK_FAILED: {s}'
    if name=='fill':
        s=str(a.get('selector','')).strip(); loc=page.locator(s)
        for i in range(loc.count()):
            try:
                e=loc.nth(i)
                if e.is_visible() and e.is_enabled(): e.fill(str(a.get('text','')),timeout=TIMEOUT); return f'FILL_SUCCESS: {s}'
            except: pass
        return f'FILL_FAILED: {s}'
    if name=='press':
        s=str(a.get('selector','')).strip(); key=str(a.get('key','Enter'))
        if not s: page.keyboard.press(key); return f'PRESS_SUCCESS: {key}'
        loc=page.locator(s)
        for i in range(loc.count()):
            try:
                e=loc.nth(i)
                if e.is_visible() and e.is_enabled(): e.press(key,timeout=TIMEOUT); return f'PRESS_SUCCESS: {key}'
            except: pass
        return f'PRESS_FAILED: {s}'
    if name=='select': page.locator(a['selector']).filter(visible=True).first.select_option(a['value'],timeout=TIMEOUT); return 'SELECT_SUCCESS'
    if name=='assert_text':
        t=page.locator('body').inner_text(timeout=4000); x=str(a.get('text','')); return f'ASSERT_TEXT_SUCCESS: {x}' if x.lower() in t.lower() else f'ASSERT_TEXT_FAILED: {x}'
    if name=='assert_url': return f"ASSERT_URL_SUCCESS: {a.get('contains')}" if a.get('contains','') in page.url else f"ASSERT_URL_FAILED: {a.get('contains')}"
    return f'UNSUPPORTED_ACTION: {name}'

SYSTEM = r'''
You are a generic ERPNext browser agent. Execute the user's natural-language task on the current browser.

CRITICAL: Return EXACTLY ONE JSON OBJECT containing ONE action. NEVER return a plan or a steps array.

Actions:
{"action":"login"}
{"action":"goto","url":"/app/home"}
{"action":"search","query":"Budget Head"}
{"action":"click_text","text":"New"}
{"action":"click","selector":"..."}
{"action":"fill","selector":"...","text":"..."}
{"action":"press","selector":"...","key":"Enter"}
{"action":"select","selector":"...","value":"..."}
{"action":"wait","ms":1000}
{"action":"read_page"}
{"action":"screenshot","name":"step"}
{"action":"assert_text","text":"..."}
{"action":"assert_url","contains":"/app"}
{"action":"done","result":"Task completed."}

RULES:
1. Python handles credentials locally. Never output or request credentials.
2. If URL contains /app or /desk, DO NOT login again.
3. Search/find/look for a document or Doctype => use the generic search action, not a CSS selector for the document name.
4. Example: search Budget Head => {"action":"search","query":"Budget Head"}
5. Use current page state as source of truth. Do not invent selectors.
6. After each action, a fresh browser state will be provided.
7. Do not repeat a failed action unchanged. Choose another method after failure.
8. Follow the exact stop condition. If user says stop after search results are visible, do not open the result.
9. Never delete/cancel/approve/submit/post/reverse or change financial data unless explicitly requested.
10. Do not perform unrelated actions.
'''

def main():
    task=input('QA task for ERPNext: ').strip()
    if not task: return
    log('='*60); log('GENERIC ERPNext AI AGENT'); log('='*60); log(f'Opening ERP: {ERP_URL}')
    report={'status':'error','task':task,'steps':0,'actions':[]}
    messages=[{'role':'system','content':SYSTEM},{'role':'user','content':f'ERPNext base URL: {ERP_URL}\nUSER TASK:\n{task}'}]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=HEADLESS,slow_mo=SLOW_MO)
        page=browser.new_page(viewport={'width':1440,'height':900})
        try:
            page.goto(ERP_URL,wait_until='domcontentloaded',timeout=30000); log(f'Current URL: {page.url}')
            if not logged_in(page): login(page)
            for step in range(1,MAX_STEPS+1):
                report['steps']=step; log(f'========== STEP {step} ==========')
                state=snapshot(page)
                prompt=f'''CURRENT LOGIN STATE: {"LOGGED_IN" if logged_in(page) else "UNKNOWN"}\nCURRENT BROWSER STATE:\n{state}\n\nUSER TASK:\n{task}\n\nReturn ONE next action only.'''
                messages.append({'role':'user','content':prompt})
                started=time.time(); raw=ask_qwen(messages); log(f'QWEN RESPONSE TIME: {time.time()-started:.2f}s'); log(f'QWEN ACTION: {raw}')
                action=parse_action(raw); log('ACTION: '+json.dumps(action,ensure_ascii=False))
                # Never allow Qwen to login twice.
                if action.get('action')=='login' and logged_in(page):
                    result='LOGIN_BLOCKED: already logged in'
                    messages.append({'role':'assistant','content':json.dumps(action)}); messages.append({'role':'user','content':result+' Choose the next task action.'}); log(result); continue
                try: result=execute(page,action)
                except Exception as e: result=f'ACTION_EXCEPTION: {type(e).__name__}: {e}'
                log(f'RESULT: {result}'); report['actions'].append({'step':step,'action':action,'result':result,'url':page.url})
                messages.append({'role':'assistant','content':json.dumps(action,ensure_ascii=False)}); messages.append({'role':'user','content':f'TOOL RESULT:\n{result}\nChoose the next action from the new browser state.'})
                if result.startswith('__DONE__'):
                    report['status']='passed'; report['result']=result[8:]; log('DONE: '+result[8:]); break
            else:
                report['status']='failed'; report['result']=f'MAX_STEPS reached ({MAX_STEPS})'
        except KeyboardInterrupt:
            report['status']='interrupted'; report['result']='Stopped by user.'; log('Interrupted by user.')
        except Exception as e:
            report['status']='error'; report['result']=str(e); log(f'FATAL ERROR: {type(e).__name__}: {e}')
            try: page.screenshot(path=str(SHOTS/'failure.png'),full_page=True)
            except: pass
        finally:
            REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            try: browser.close()
            except: pass
    log('='*60); log(f"STATUS: {report['status']}"); log(f"STEPS: {report['steps']}"); log(f'REPORT: {REPORT}'); log('='*60)

if __name__=='__main__': main()
