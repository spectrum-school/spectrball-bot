FROM python:3.11-slim 

WORKDIR /app 

# Устанавливаем зависимости 
COPY requirements.txt . 

RUN pip install --no-cache-dir -r requirements.txt 

# Копируем код 
COPY . . 

# Команда запуска 
CMD ["python", "main.py"]
