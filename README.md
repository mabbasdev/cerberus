# Cerberus 🐺 — A Three-Headed Guard for Your Desktop

> _In Greek mythology, Cerberus guards the gates of the Underworld.
> In this project, Cerberus guards your desktop with three layers of
> authentication: your OS password, an authorized USB, and a live
> folder challenge on your Desktop._

## Layers

| Layer | Name        | What it checks                                 |
| ----- | ----------- | ---------------------------------------------- |
| 1     | OS Login    | Handled by the operating system                |
| 2     | USB Head    | An authorized USB (by serial) is plugged in    |
| 3     | Folder Head | You create `unlock` on your Desktop within 5 s |

Failure at layer 2 or 3 → **immediate shutdown** (simulated in `DEV_MODE`).

## Dev Setup

```bash
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```
