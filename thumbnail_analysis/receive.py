
import pika
import image

credentials = pika.PlainCredentials('muna', 'muna112358!')
connection = pika.BlockingConnection(pika.ConnectionParameters('13.124.107.195', 5672, '/',
                                                               credentials, heartbeat=0,
                                                               blocked_connection_timeout=None))
channel = connection.channel()
channel.basic_qos(prefetch_count=1)


def callback(ch, method, properties, body):
    print(" [x] Received %r" % body.decode())
    if image.main(body.decode()):
        channel.basic_ack(delivery_tag=method.delivery_tag, multiple=False)
    else:
        channel.basic_nack(delivery_tag=method.delivery_tag, multiple=False,requeue=False)
        


# auto_ack를 False로 수정했습니다.
# auto_ack가 True일 경우 메세지를 꺼내오는 순간에 메세지 큐에서 해당 메세지는 삭제됩니다.
# 만약 해당 주소를 크롤러가 받아와서 도는 도중에 크롤러가 중간에 에러를 띄우고
# 프로세스가 중간에 죽어버릴 경우 정상적으로 처리가 안되었지만 메세지 큐에는 해당 주소가 없는 상황이 발생합니다.
channel.basic_consume(queue='test_URL', on_message_callback=callback, auto_ack=False)

print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()