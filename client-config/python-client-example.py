#!/usr/bin/env python3
"""
Example Python Kafka client using mTLS authentication
Requires: pip install kafka-python
"""

from kafka import KafkaProducer, KafkaConsumer
import ssl
import os

# Kafka broker configuration
# Replace with your OpenShift router domain
BOOTSTRAP_SERVERS = 'kafka-bootstrap.apps.your-domain.com:443'

# Certificate paths (extracted using extract-certificates.sh)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CA_CERT_PATH = os.path.join(SCRIPT_DIR, 'certs/ca.crt')
CLIENT_CERT_PATH = os.path.join(SCRIPT_DIR, 'certs/user.crt')
CLIENT_KEY_PATH = os.path.join(SCRIPT_DIR, 'certs/user.key')

def create_ssl_context():
    """Create SSL context for mTLS authentication"""
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=CA_CERT_PATH)
    context.load_cert_chain(certfile=CLIENT_CERT_PATH, keyfile=CLIENT_KEY_PATH)
    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED
    return context

def produce_messages():
    """Example producer with mTLS"""
    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        security_protocol='SSL',
        ssl_context=create_ssl_context(),
        # Optional producer configs
        acks='all',
        retries=3,
        max_in_flight_requests_per_connection=5,
        value_serializer=lambda v: v.encode('utf-8')
    )

    # Send messages
    for i in range(10):
        message = f'Test message {i}'
        future = producer.send('test-topic', value=message)
        record_metadata = future.get(timeout=10)
        print(f'Sent: {message} to {record_metadata.topic} partition {record_metadata.partition} offset {record_metadata.offset}')

    producer.flush()
    producer.close()
    print('Producer finished')

def consume_messages():
    """Example consumer with mTLS"""
    consumer = KafkaConsumer(
        'test-topic',
        bootstrap_servers=BOOTSTRAP_SERVERS,
        security_protocol='SSL',
        ssl_context=create_ssl_context(),
        # Consumer configs
        group_id='external-client-group',
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        value_deserializer=lambda m: m.decode('utf-8')
    )

    print('Consumer started, waiting for messages...')

    try:
        for message in consumer:
            print(f'Received: {message.value} from partition {message.partition} offset {message.offset}')
            consumer.commit()
    except KeyboardInterrupt:
        print('Consumer stopped')
    finally:
        consumer.close()

if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Usage: python3 python-client-example.py [produce|consume]')
        sys.exit(1)

    mode = sys.argv[1]

    if mode == 'produce':
        produce_messages()
    elif mode == 'consume':
        consume_messages()
    else:
        print('Invalid mode. Use "produce" or "consume"')
        sys.exit(1)
