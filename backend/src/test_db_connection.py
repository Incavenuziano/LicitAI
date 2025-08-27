import psycopg2
import os

print("Current working directory:", os.getcwd())

try:
    print("Attempting to connect to the database...")
    dsn_string = "host=localhost port=5432 dbname=licitai user=postgres password=postgres client_encoding=utf8 application_name=LicitAI_Test_Connection service=''"
    conn = psycopg2.connect(dsn_string)
    print("Connection successful!")
    conn.close()
except Exception as e:
    print("An error occurred:", e)