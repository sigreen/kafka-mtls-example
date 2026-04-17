import org.apache.kafka.clients.producer.KafkaProducer;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.clients.producer.RecordMetadata;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecords;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.common.serialization.StringSerializer;
import org.apache.kafka.common.serialization.StringDeserializer;

import java.time.Duration;
import java.util.Collections;
import java.util.Properties;
import java.util.concurrent.ExecutionException;

/**
 * Example Java Kafka client using mTLS authentication
 *
 * Maven dependencies:
 * <dependency>
 *   <groupId>org.apache.kafka</groupId>
 *   <artifactId>kafka-clients</artifactId>
 *   <version>3.8.0</version>
 * </dependency>
 */
public class JavaClientExample {

    // Replace with your OpenShift router domain
    private static final String BOOTSTRAP_SERVERS = "kafka-bootstrap.apps.your-domain.com:443";
    private static final String TOPIC = "test-topic";

    // Certificate paths (update these with actual paths from extract-certificates.sh)
    private static final String TRUSTSTORE_PATH = "./certs/truststore.p12";
    private static final String TRUSTSTORE_PASSWORD = "<truststore-password>";
    private static final String KEYSTORE_PATH = "./certs/user.p12";
    private static final String KEYSTORE_PASSWORD = "<keystore-password>";

    public static Properties createCommonProperties() {
        Properties props = new Properties();

        // Kafka cluster
        props.put(ProducerConfig.BOOTSTRAP_SERVERS_CONFIG, BOOTSTRAP_SERVERS);

        // Security configuration for mTLS
        props.put("security.protocol", "SSL");

        // Truststore configuration (cluster CA)
        props.put("ssl.truststore.location", TRUSTSTORE_PATH);
        props.put("ssl.truststore.password", TRUSTSTORE_PASSWORD);
        props.put("ssl.truststore.type", "PKCS12");

        // Keystore configuration (client certificate)
        props.put("ssl.keystore.location", KEYSTORE_PATH);
        props.put("ssl.keystore.password", KEYSTORE_PASSWORD);
        props.put("ssl.keystore.type", "PKCS12");

        // SSL protocol configuration
        props.put("ssl.protocol", "TLSv1.3");
        props.put("ssl.enabled.protocols", "TLSv1.3,TLSv1.2");

        // Optional: hostname verification
        props.put("ssl.endpoint.identification.algorithm", "https");

        return props;
    }

    public static void produceMessages() throws ExecutionException, InterruptedException {
        Properties props = createCommonProperties();

        // Producer-specific configuration
        props.put(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG, StringSerializer.class.getName());
        props.put(ProducerConfig.ACKS_CONFIG, "all");
        props.put(ProducerConfig.RETRIES_CONFIG, 3);
        props.put(ProducerConfig.MAX_IN_FLIGHT_REQUESTS_PER_CONNECTION, 5);
        props.put(ProducerConfig.ENABLE_IDEMPOTENCE_CONFIG, true);
        props.put(ProducerConfig.COMPRESSION_TYPE_CONFIG, "snappy");

        try (KafkaProducer<String, String> producer = new KafkaProducer<>(props)) {
            System.out.println("Starting producer with mTLS...");

            for (int i = 0; i < 10; i++) {
                String key = "key-" + i;
                String value = "Test message " + i;

                ProducerRecord<String, String> record = new ProducerRecord<>(TOPIC, key, value);

                // Synchronous send
                RecordMetadata metadata = producer.send(record).get();

                System.out.printf("Sent: %s to partition %d with offset %d%n",
                    value, metadata.partition(), metadata.offset());
            }

            producer.flush();
            System.out.println("Producer finished successfully");
        }
    }

    public static void consumeMessages() {
        Properties props = createCommonProperties();

        // Consumer-specific configuration
        props.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        props.put(ConsumerConfig.GROUP_ID_CONFIG, "external-client-group");
        props.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
        props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 100);

        try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(props)) {
            consumer.subscribe(Collections.singletonList(TOPIC));

            System.out.println("Starting consumer with mTLS...");
            System.out.println("Subscribed to topic: " + TOPIC);

            while (true) {
                ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(1000));

                for (ConsumerRecord<String, String> record : records) {
                    System.out.printf("Received: key=%s, value=%s, partition=%d, offset=%d%n",
                        record.key(), record.value(), record.partition(), record.offset());
                }

                if (!records.isEmpty()) {
                    consumer.commitSync();
                }
            }
        } catch (Exception e) {
            System.err.println("Error in consumer: " + e.getMessage());
            e.printStackTrace();
        }
    }

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Usage: java JavaClientExample [produce|consume]");
            System.exit(1);
        }

        String mode = args[0];

        try {
            if ("produce".equals(mode)) {
                produceMessages();
            } else if ("consume".equals(mode)) {
                consumeMessages();
            } else {
                System.err.println("Invalid mode. Use 'produce' or 'consume'");
                System.exit(1);
            }
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }
}
