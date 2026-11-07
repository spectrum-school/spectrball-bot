FROM python:3.11-slim

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код бота
COPY . .

# Создаем папку для данных, если ее нет (дублирует страховку из main.py)
RUN mkdir -p schools/school_1

# Команда запуска
CMD ["python", "main.py"]
