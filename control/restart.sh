sudo kill -9 `lsof -ti:27431`
nohup /home/orangepi/bot/.venv/bin/python main.py > log/output.log