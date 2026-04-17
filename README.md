# Kafka mTLS on Self-Managed OpenShift 4.20 (Azure)

Complete configuration for deploying Red Hat Streams for Apache Kafka 3.1 with mutual TLS (mTLS) authentication on self-managed OpenShift 4.20 running on Azure.

## Overview

- **Platform**: Self-managed OpenShift 4.20 on Azure (not ARO)
- **Kafka**: Streams for Apache Kafka 3.1 (Strimzi operator)
- **Kafka Version**: 4.1.0 in **KRaft mode** (no ZooKeeper)
- **Architecture**: 3 broker nodes + 3 controller nodes (KafkaNodePools)
- **Authentication**: mTLS with Strimzi auto-generated self-signed certificates
- **Authorization**: Simple ACL authorization enabled
- **Storage**: Configurable (Azure Managed Disks or OpenShift Container Storage)
- **External Access**: OpenShift Routes with TLS passthrough
- **High Availability**: Multi-node deployment across availability zones

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  OpenShift 4.20 on Azure                     │
│                                                               │
│  ┌────────────────────────────────────────────────────┐      │
│  │              Kafka Namespace                       │      │
│  │                                                      │      │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐            │      │
│  │  │ Kafka-0 │  │ Kafka-1 │  │ Kafka-2 │            │      │
│  │  │ (mTLS)  │  │ (mTLS)  │  │ (mTLS)  │            │      │
│  │  └────┬────┘  └────┬────┘  └────┬────┘            │      │
│  │       │            │            │                  │      │
│  │       └────────────┴────────────┘                  │      │
│  │                    │                               │      │
│  │              ┌─────▼─────┐                         │      │
│  │              │  Routes   │  (TLS Passthrough)      │      │
│  │              └─────┬─────┘                         │      │
│  └────────────────────┼─────────────────────────────┘      │
│                       │                                     │
└───────────────────────┼─────────────────────────────────────┘
                        │
                  mTLS Port 443
                        │
                  ┌─────▼─────┐
                  │  External │
                  │  Client   │
                  │  (cert)   │
                  └───────────┘
```

## Prerequisites

- [x] Self-managed OpenShift 4.20 cluster on Azure
- [x] Red Hat Streams for Apache Kafka 3.1 Operator installed
  - **Supported Kafka versions**: 4.0.0, 4.1.0 (ZooKeeper-based clusters not supported)
  - **This guide uses Kafka 4.1.0 in KRaft mode**
- [x] `oc` CLI installed and authenticated
- [x] Storage class configured (OpenShift Container Storage or Azure Managed Disks)
- [x] DNS configured for OpenShift router domain
- [x] Sufficient resources: 6 pods total (3 brokers + 3 controllers) + entity operator

## Quick Start

### 1. Get Your Router Domain

```bash
oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}'
```

Example output: `apps.ocp-cluster.eastus.azure.example.com`

### 2. Update Configuration Files

Update the following files, replacing `apps.your-domain.com` with your actual router domain:
- `kafka-cluster-mtls.yaml` (bootstrap and broker hosts)
- `client-config/client.properties`
- `client-config/python-client-example.py`
- `client-config/JavaClientExample.java`

**Quick update script:**
```bash
ROUTER_DOMAIN=$(oc get ingresses.config.openshift.io cluster -o jsonpath='{.spec.domain}')
sed -i "" "s/apps.your-domain.com/${ROUTER_DOMAIN}/g" kafka-cluster-mtls.yaml
sed -i "" "s/apps.your-domain.com/${ROUTER_DOMAIN}/g" client-config/client.properties
sed -i "" "s/apps.your-domain.com/${ROUTER_DOMAIN}/g" client-config/python-client-example.py
sed -i "" "s/apps.your-domain.com/${ROUTER_DOMAIN}/g" client-config/JavaClientExample.java
```

### 3. Verify Storage Class

Check your available storage class:
```bash
oc get storageclass
```

Update `kafka-node-pool.yaml` with your storage class. Common options:
- **Azure**: `managed-premium` (Azure Premium SSD)
- **OpenShift Container Storage**: `ocs-external-storagecluster-ceph-rbd`
- **AWS**: `gp3-csi`

### 4. Deploy Kafka Cluster

```bash
# Create namespace
oc new-project kafka

# Deploy KafkaNodePools first (defines broker & controller pools)
oc apply -f kafka-node-pool.yaml

# Deploy Kafka cluster (KRaft mode)
oc apply -f kafka-cluster-mtls.yaml

# Wait for cluster to be ready (5-10 minutes)
oc wait kafka/my-cluster --for=condition=Ready --timeout=600s -n kafka
```

**What happens during deployment:**
- Strimzi operator creates 3 Kafka broker nodes + 3 controller nodes (KRaft mode)
- Auto-generates Cluster CA certificate (signs broker certs)
- Auto-generates Clients CA certificate (signs client certs)
- Creates OpenShift Routes for external access
- No ZooKeeper needed (using KRaft for metadata management)

### 5. Create Kafka User with mTLS

```bash
oc apply -f kafka-user-mtls.yaml
```

Strimzi automatically generates:
- Client certificate signed by Clients CA
- Private key
- PKCS12 keystore
- Stores in secret `external-client`

### 6. Extract Client Certificates

```bash
cd client-config
./extract-certificates.sh
```

**Generated files in `./certs/`:**
- `truststore.p12` - Cluster CA (verify broker identity)
- `user.p12` - Client certificate + private key
- `ca.crt`, `user.crt`, `user.key` - PEM format
- `*.password` files - Keystore passwords

### 7. Verify Setup

```bash
cd ..
./verify-mtls-setup.sh
```

This checks:
- ✓ Kafka cluster health
- ✓ Pods running
- ✓ Routes configured
- ✓ Certificates generated
- ✓ TLS connectivity

### 8. Test Connection

**Get bootstrap server:**
```bash
BOOTSTRAP_SERVER=$(oc get kafka my-cluster -n kafka -o jsonpath='{.status.listeners[?(@.name=="external")].bootstrapServers}')
echo $BOOTSTRAP_SERVER
```

**Test with console producer:**
```bash
# Download Kafka binaries (if not installed)
curl -O https://archive.apache.org/dist/kafka/4.1.0/kafka_2.13-4.1.0.tgz
tar -xzf kafka_2.13-4.1.0.tgz
cd kafka_2.13-4.1.0

# Start producer
bin/kafka-console-producer.sh \
  --bootstrap-server $BOOTSTRAP_SERVER \
  --topic test-topic \
  --producer.config ../client-config/client.properties
```

**Test with console consumer (separate terminal):**
```bash
bin/kafka-console-consumer.sh \
  --bootstrap-server $BOOTSTRAP_SERVER \
  --topic test-topic \
  --from-beginning \
  --consumer.config ../client-config/client.properties
```

## File Structure

```
kafka-mtls-example/
├── kafka-cluster-mtls.yaml              # Kafka cluster (Routes, KRaft mode)
├── kafka-cluster-mtls-loadbalancer.yaml # Alternative (LoadBalancer, KRaft mode)
├── kafka-node-pool.yaml                 # KafkaNodePools (3 brokers + 3 controllers)
├── kafka-user-mtls.yaml                 # User with mTLS auth
├── client-config/
│   ├── client.properties                # Java/CLI client config
│   ├── extract-certificates.sh          # Extract certs from secrets
│   ├── python-client-example.py         # Python producer/consumer
│   └── JavaClientExample.java           # Java producer/consumer
├── verify-mtls-setup.sh                 # Deployment verification
└── README.md                            # This file
```

## KRaft Mode Architecture

Kafka 4.x uses **KRaft** (Kafka Raft) instead of ZooKeeper:

- **Broker Nodes** (3): Handle client requests, store data
- **Controller Nodes** (3): Manage cluster metadata via Raft consensus
- **No ZooKeeper**: Simplified architecture, better scalability
- **KafkaNodePools**: Separate resource pools for brokers and controllers

## Kafka Configuration Details

### Listeners

| Name | Port | Type | TLS | Auth | Purpose |
|------|------|------|-----|------|---------|
| plain | 9092 | internal | No | None | Internal plaintext |
| tls | 9093 | internal | Yes | mTLS | Internal encrypted |
| external | 9094 | route | Yes | mTLS | External client access |

### External Access Routes

Each broker gets a dedicated route:
- **Bootstrap**: `kafka-bootstrap.apps.your-domain.com:443`
- **Broker 0**: `kafka-broker-0.apps.your-domain.com:443`
- **Broker 1**: `kafka-broker-1.apps.your-domain.com:443`
- **Broker 2**: `kafka-broker-2.apps.your-domain.com:443`

Routes use **TLS passthrough** - OpenShift router forwards encrypted traffic directly to Kafka brokers without terminating TLS.

### Certificate Management (Automatic)

Strimzi handles all certificate lifecycle management:

| Certificate | Secret Name | Purpose | Validity | Auto-Renewal |
|-------------|-------------|---------|----------|--------------|
| Cluster CA | `my-cluster-cluster-ca-cert` | Sign broker certs | 365 days | 30 days before expiry |
| Clients CA | `my-cluster-clients-ca-cert` | Sign client certs | 365 days | 30 days before expiry |
| User Cert | `external-client` | Client authentication | 365 days | 30 days before expiry |

**Configuration in `kafka-cluster-mtls.yaml`:**
```yaml
clientsCa:
  generateCertificateAuthority: true  # Auto-generate
  renewalDays: 30                     # Renew 30 days before expiry
  validityDays: 365                   # Valid for 1 year
clusterCa:
  generateCertificateAuthority: true
  renewalDays: 30
  validityDays: 365
```

## Client Examples

### Java/Kafka CLI

Configuration in `client-config/client.properties`:

```properties
bootstrap.servers=kafka-bootstrap.apps.your-domain.com:443
security.protocol=SSL
ssl.truststore.location=./certs/truststore.p12
ssl.truststore.password=<from-extract-script>
ssl.keystore.location=./certs/user.p12
ssl.keystore.password=<from-extract-script>
ssl.keystore.type=PKCS12
ssl.truststore.type=PKCS12
ssl.protocol=TLSv1.3
```

### Python

Install dependencies:
```bash
pip install kafka-python
```

**Producer:**
```bash
python3 client-config/python-client-example.py produce
```

**Consumer:**
```bash
python3 client-config/python-client-example.py consume
```

See `client-config/python-client-example.py` for full implementation.

### Java Application

```java
Properties props = new Properties();
props.put("bootstrap.servers", "kafka-bootstrap.apps.your-domain.com:443");
props.put("security.protocol", "SSL");
props.put("ssl.truststore.location", "./certs/truststore.p12");
props.put("ssl.truststore.password", "truststore-password");
props.put("ssl.keystore.location", "./certs/user.p12");
props.put("ssl.keystore.password", "user-password");
props.put("ssl.keystore.type", "PKCS12");
props.put("ssl.truststore.type", "PKCS12");

KafkaProducer<String, String> producer = new KafkaProducer<>(props);
```

See `client-config/JavaClientExample.java` for full implementation.

## Production Considerations

### Resource Sizing

**Minimum worker node specs:**
- VM Size: `Standard_D4s_v4` or larger
- vCPUs: 4+
- Memory: 16GB+
- Network: Accelerated networking enabled
- Nodes: 5+ (for redundancy beyond 3 brokers)

**Kafka broker resources (production):**
```yaml
resources:
  requests:
    memory: 8Gi
    cpu: 2000m
  limits:
    memory: 8Gi
    cpu: 4000m
```

### Scaling

**Increase broker count:**
```yaml
spec:
  kafka:
    replicas: 5  # Increase from 3
```

Apply changes:
```bash
oc apply -f kafka-cluster-mtls.yaml
```

### Monitoring

**Enable Prometheus metrics:**
```yaml
spec:
  kafka:
    metricsConfig:
      type: jmxPrometheusExporter
      valueFrom:
        configMapKeyRef:
          name: kafka-metrics
          key: kafka-metrics-config.yml
```

**Monitor key metrics:**
- Disk IOPS and throughput (Azure)
- Network throughput
- CPU/Memory utilization
- Kafka lag, request rate, error rate

### Backup Strategy

**Azure Disk snapshots:**
```bash
# List PVCs
oc get pvc -n kafka

# Create snapshot via Azure CLI
az snapshot create \
  --resource-group <resource-group> \
  --source <disk-id> \
  --name kafka-backup-$(date +%Y%m%d)
```

**Alternative: Velero with Azure Blob Storage**

## Troubleshooting

### Cluster Not Ready

```bash
# Check pod status
oc get pods -n kafka

# View logs
oc logs my-cluster-kafka-0 -n kafka

# Describe cluster
oc describe kafka my-cluster -n kafka

# Check events
oc get events -n kafka --sort-by='.lastTimestamp'
```

### Routes Not Accessible

```bash
# Check routes
oc get routes -n kafka
oc describe route my-cluster-kafka-bootstrap -n kafka

# Test DNS
nslookup kafka-bootstrap.apps.your-domain.com

# Verify router pods
oc get pods -n openshift-ingress
```

### Certificate Issues

```bash
# View cluster CA
oc get secret my-cluster-cluster-ca-cert -n kafka -o jsonpath='{.data.ca\.crt}' | base64 -d | openssl x509 -text -noout

# View user cert
oc get secret external-client -n kafka -o jsonpath='{.data.user\.crt}' | base64 -d | openssl x509 -text -noout

# Verify cert chain
openssl verify -CAfile ./certs/ca.crt ./certs/user.crt

# Test TLS handshake
openssl s_client -connect kafka-bootstrap.apps.your-domain.com:443 \
  -cert ./certs/user.crt -key ./certs/user.key -CAfile ./certs/ca.crt
```

### Storage Issues

```bash
# Check PVCs
oc get pvc -n kafka

# Check storage class
oc get storageclass

# View Azure disk metrics
az monitor metrics list \
  --resource <disk-resource-id> \
  --metric "Composite Disk Read IOPS" "Composite Disk Write IOPS"
```

### Common Issues

| Issue | Symptom | Solution |
|-------|---------|----------|
| PVC Pending | Pods not starting | Check storage class exists: `oc get sc` |
| Route not accessible | Connection timeout | Verify DNS and router pods |
| Certificate verification failed | SSL errors | Check truststore contains correct CA |
| Authentication failed | Permission denied | Ensure client cert signed by clients CA |
| Disk performance | Slow writes | Upgrade to larger disk size (more IOPS) |

## Security Best Practices

1. **mTLS Enforced**: All external clients must present valid certificates
2. **Strong Ciphers**: TLS 1.3/1.2 only, AES-256-GCM, AES-128-GCM
3. **Auto Certificate Rotation**: Certificates renewed 30 days before expiry
4. **ACLs**: Configure per-user topic permissions in `kafka-user-mtls.yaml`
5. **Network Policies**: Add OpenShift NetworkPolicies for pod isolation
6. **Azure Security**:
   - Use Azure Key Vault for sensitive data
   - Enable Azure Defender for threat detection
   - Configure NSGs to limit access
   - Use Azure Private Link for internal connectivity

## Advanced Configuration

### Create Additional Users

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaUser
metadata:
  name: app-producer
  namespace: kafka
  labels:
    strimzi.io/cluster: my-cluster
spec:
  authentication:
    type: tls
  authorization:
    type: simple
    acls:
      - resource:
          type: topic
          name: app-events
          patternType: literal
        operations:
          - Write
          - Describe
        host: "*"
```

Apply:
```bash
oc apply -f app-producer.yaml
```

Extract certs:
```bash
oc get secret app-producer -n kafka -o jsonpath='{.data.user\.p12}' | base64 -d > app-producer.p12
```

### Configure Topic Auto-Creation

```yaml
spec:
  kafka:
    config:
      auto.create.topics.enable: true
      default.replication.factor: 3
      min.insync.replicas: 2
      num.partitions: 3
```

### Enable Rack Awareness

```yaml
spec:
  kafka:
    rack:
      topologyKey: topology.kubernetes.io/zone
```

## Cleanup

**Warning**: This deletes all Kafka data permanently.

```bash
# Delete user
oc delete kafkauser external-client -n kafka

# Delete Kafka cluster (deletes all data)
oc delete kafka my-cluster -n kafka

# Delete namespace
oc delete project kafka
```

## References

- [Red Hat Streams for Apache Kafka 3.1 Documentation](https://docs.redhat.com/en/documentation/red_hat_streams_for_apache_kafka/3.1)
- [Strimzi Documentation](https://strimzi.io/docs/operators/latest/overview)
- [Apache Kafka Security](https://kafka.apache.org/documentation/#security)
- [OpenShift 4.20 on Azure](https://docs.openshift.com/container-platform/4.20/installing/installing_azure/preparing-to-install-on-azure.html)
- [Azure Managed Disks](https://docs.microsoft.com/azure/virtual-machines/managed-disks-overview)

## License

This example configuration is provided as-is for educational purposes.
