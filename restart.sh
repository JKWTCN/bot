sudo kill -9 `lsof -ti:27431`
sudo kill -9 `lsof -ti:27432`
nohup /home/orangepi/bot/.venv/bin/python main.py > log/output.log
nohup /home/orangepi/bot/.venv/bin/python main_chat.py > log/chat_output.log