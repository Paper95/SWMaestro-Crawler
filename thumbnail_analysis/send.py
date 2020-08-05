#!/usr/bin/env python
import pika
import psycopg2 as pg2
import loadUrls as lu

credentials = pika.PlainCredentials('muna', 'muna112358!')
connection = pika.BlockingConnection(pika.ConnectionParameters('13.124.107.195', 5672, '/', credentials))
channel = connection.channel()

urls = lu.loadUrls()
for url in urls:
    channel.basic_publish(exchange='test_exchange',
                          routing_key='test_URL',
                          body=url)
print("Sending completed")

connection.close()