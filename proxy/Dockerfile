FROM python:3.11
RUN apt update -y && apt install -y moreutils
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY monitor.py /monitor.py
CMD ["python", "-u", "monitor.py"]