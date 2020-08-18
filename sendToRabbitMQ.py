#!/usr/bin/env python
import pika
import psycopg2 as pg2


def loadUrls():
    conn = None
    try:
        conn = pg2.connect(database="createtrend", user="muna", password="muna112358!", host="13.124.107.195",
                           port="5432")
        cur = conn.cursor()
        # cur.execute("SELECT upload_id from channel;")
        cur.execute(
            # f"""SELECT upload_id FROM channel WHERE status = TRUE"""   # 채널의 새로운 비디오 갱신, New_Video_Inserter
            # f"""SELECT channel_id FROM channel WHERE status = TRUE"""   # 채널의 구독자수등의 정보 갱신, Channel_Updater
            f"""SELECT video_id FROM video WHERE CURRENT_TIMESTAMP - upload_time <= INTERVAL '1 month' AND status = TRUE AND forbidden = FALSE;"""  # 비디오 조회수 갱신, APP_proxy
            # """SELECT channel_id FROM channel;"""
        )
            # """SELECT video_id FROM video WHERE upload_time BETWEEN CURRENT_TIMESTAMP - interval '3 MONTH' AND now();""")
            # """SELECT DISTINCT video_id from video A LEFT JOIN video_views B ON A.idx = B.video_idx WHERE B.video_idx is NULL AND A.forbidden = FALSE;""")
        rows = cur.fetchall()
        newrows = [row[0] for row in rows]
        [print(row) for row in newrows]
        return newrows

    except Exception as e:
        print("postgresql database conn error")
        print(e)
    finally:
        if conn:
            conn.close()


credentials = pika.PlainCredentials('muna', 'muna112358!')
connection = pika.BlockingConnection(pika.ConnectionParameters('13.124.107.195', 5672, '/', credentials))
channel = connection.channel()

urls = loadUrls()
for url in urls:
    channel.basic_publish(exchange='',
                          routing_key='URL2',
                          body=url)
print("Sending completed")

connection.close()
