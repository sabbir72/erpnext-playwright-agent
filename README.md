# ERPNext + Playwright + Ollama AI Agent

This starter project connects a local Ollama model to Playwright so an AI agent can inspect and operate an ERPNext browser.

## 1. Create environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

## 2. Configure

```bash
cp .env.example .env
nano .env
```

Set your real ERPNext URL and credentials.

## 3. Make sure Ollama is running

```bash
ollama serve
```

In another terminal:

```bash
ollama list
```

You should see `qwen2.5-coder:7b`.

## 4. Run the agent

```bash
python agent.py
```

Example task:

`Login to ERPNext and open the Users list.`

The agent uses a small set of browser tools:
- goto
- click
- fill
- press
- select
- read_page
- screenshot
- wait

It asks the local Ollama model what action to take next and executes the action in Playwright.

## 5. Run the basic Playwright smoke test

```bash
pytest -q
```

## Important

This is a starter agent, not a production autonomous QA system. Keep destructive ERPNext actions disabled until you add your own approval rules. Never put real credentials into source code or commit `.env`.
