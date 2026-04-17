#!/bin/bash
# Verification script for Kafka mTLS setup on OpenShift
# This script checks the deployment and validates mTLS configuration

set -e

NAMESPACE="kafka"
CLUSTER_NAME="my-cluster"
USER_NAME="external-client"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Kafka mTLS Setup Verification"
echo "=========================================="
echo ""

# Function to check command exists
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}✗${NC} $1 is not installed"
        exit 1
    else
        echo -e "${GREEN}✓${NC} $1 is available"
    fi
}

# Check prerequisites
echo "Checking prerequisites..."
check_command oc
check_command openssl
echo ""

# Check if logged into OpenShift
echo "Checking OpenShift connection..."
if oc whoami &> /dev/null; then
    echo -e "${GREEN}✓${NC} Logged into OpenShift as $(oc whoami)"
    echo -e "${GREEN}✓${NC} Current project: $(oc project -q)"
else
    echo -e "${RED}✗${NC} Not logged into OpenShift"
    exit 1
fi
echo ""

# Check if namespace exists
echo "Checking namespace..."
if oc get namespace "$NAMESPACE" &> /dev/null; then
    echo -e "${GREEN}✓${NC} Namespace '$NAMESPACE' exists"
else
    echo -e "${RED}✗${NC} Namespace '$NAMESPACE' does not exist"
    exit 1
fi
echo ""

# Check Kafka cluster status
echo "Checking Kafka cluster..."
if oc get kafka "$CLUSTER_NAME" -n "$NAMESPACE" &> /dev/null; then
    echo -e "${GREEN}✓${NC} Kafka cluster '$CLUSTER_NAME' exists"

    KAFKA_READY=$(oc get kafka "$CLUSTER_NAME" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
    if [ "$KAFKA_READY" = "True" ]; then
        echo -e "${GREEN}✓${NC} Kafka cluster is Ready"
    else
        echo -e "${YELLOW}!${NC} Kafka cluster is not Ready yet"
        oc get kafka "$CLUSTER_NAME" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")]}'
        echo ""
    fi
else
    echo -e "${RED}✗${NC} Kafka cluster '$CLUSTER_NAME' does not exist"
    exit 1
fi
echo ""

# Check pods
echo "Checking Kafka pods..."
KAFKA_PODS=$(oc get pods -n "$NAMESPACE" -l strimzi.io/cluster="$CLUSTER_NAME",strimzi.io/kind=Kafka --no-headers 2>/dev/null | wc -l)
if [ "$KAFKA_PODS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Found $KAFKA_PODS Kafka broker pods"
    oc get pods -n "$NAMESPACE" -l strimzi.io/cluster="$CLUSTER_NAME",strimzi.io/kind=Kafka
else
    echo -e "${RED}✗${NC} No Kafka broker pods found"
fi
echo ""

# Check ZooKeeper pods
ZOOKEEPER_PODS=$(oc get pods -n "$NAMESPACE" -l strimzi.io/cluster="$CLUSTER_NAME",strimzi.io/kind=Kafka,strimzi.io/name="${CLUSTER_NAME}-zookeeper" --no-headers 2>/dev/null | wc -l)
if [ "$ZOOKEEPER_PODS" -gt 0 ]; then
    echo -e "${GREEN}✓${NC} Found $ZOOKEEPER_PODS ZooKeeper pods"
else
    echo -e "${YELLOW}!${NC} No ZooKeeper pods found (might be using KRaft mode)"
fi
echo ""

# Check external listener configuration
echo "Checking external listener..."
EXTERNAL_LISTENER=$(oc get kafka "$CLUSTER_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.kafka.listeners[?(@.name=="external")]}')
if [ -n "$EXTERNAL_LISTENER" ]; then
    echo -e "${GREEN}✓${NC} External listener is configured"

    LISTENER_TYPE=$(oc get kafka "$CLUSTER_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.kafka.listeners[?(@.name=="external")].type}')
    echo "  Type: $LISTENER_TYPE"

    AUTH_TYPE=$(oc get kafka "$CLUSTER_NAME" -n "$NAMESPACE" -o jsonpath='{.spec.kafka.listeners[?(@.name=="external")].authentication.type}')
    if [ "$AUTH_TYPE" = "tls" ]; then
        echo -e "${GREEN}✓${NC} mTLS authentication is enabled"
    else
        echo -e "${YELLOW}!${NC} Authentication type: $AUTH_TYPE (expected: tls)"
    fi
else
    echo -e "${RED}✗${NC} No external listener configured"
fi
echo ""

# Check bootstrap server
echo "Checking bootstrap server..."
BOOTSTRAP_SERVER=$(oc get kafka "$CLUSTER_NAME" -n "$NAMESPACE" -o jsonpath='{.status.listeners[?(@.name=="external")].bootstrapServers}')
if [ -n "$BOOTSTRAP_SERVER" ]; then
    echo -e "${GREEN}✓${NC} Bootstrap server: $BOOTSTRAP_SERVER"
else
    echo -e "${RED}✗${NC} Bootstrap server not found in status"
fi
echo ""

# Check Routes or Services
if [ "$LISTENER_TYPE" = "route" ]; then
    echo "Checking OpenShift Routes..."
    ROUTES=$(oc get routes -n "$NAMESPACE" -l strimzi.io/cluster="$CLUSTER_NAME" --no-headers 2>/dev/null | wc -l)
    if [ "$ROUTES" -gt 0 ]; then
        echo -e "${GREEN}✓${NC} Found $ROUTES routes"
        oc get routes -n "$NAMESPACE" -l strimzi.io/cluster="$CLUSTER_NAME"
    else
        echo -e "${RED}✗${NC} No routes found"
    fi
elif [ "$LISTENER_TYPE" = "loadbalancer" ]; then
    echo "Checking LoadBalancer Services..."
    SERVICES=$(oc get svc -n "$NAMESPACE" -l strimzi.io/cluster="$CLUSTER_NAME" --no-headers 2>/dev/null | wc -l)
    if [ "$SERVICES" -gt 0 ]; then
        echo -e "${GREEN}✓${NC} Found $SERVICES services"
        oc get svc -n "$NAMESPACE" -l strimzi.io/cluster="$CLUSTER_NAME"
    else
        echo -e "${RED}✗${NC} No services found"
    fi
fi
echo ""

# Check CA certificates
echo "Checking CA certificates..."
if oc get secret "${CLUSTER_NAME}-cluster-ca-cert" -n "$NAMESPACE" &> /dev/null; then
    echo -e "${GREEN}✓${NC} Cluster CA certificate secret exists"

    # Extract and display CA cert info
    CA_CERT=$(oc get secret "${CLUSTER_NAME}-cluster-ca-cert" -n "$NAMESPACE" -o jsonpath='{.data.ca\.crt}' | base64 -d)
    echo "$CA_CERT" | openssl x509 -noout -subject -dates
else
    echo -e "${RED}✗${NC} Cluster CA certificate secret not found"
fi
echo ""

if oc get secret "${CLUSTER_NAME}-clients-ca-cert" -n "$NAMESPACE" &> /dev/null; then
    echo -e "${GREEN}✓${NC} Clients CA certificate secret exists"
else
    echo -e "${RED}✗${NC} Clients CA certificate secret not found"
fi
echo ""

# Check KafkaUser
echo "Checking KafkaUser..."
if oc get kafkauser "$USER_NAME" -n "$NAMESPACE" &> /dev/null; then
    echo -e "${GREEN}✓${NC} KafkaUser '$USER_NAME' exists"

    USER_READY=$(oc get kafkauser "$USER_NAME" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}')
    if [ "$USER_READY" = "True" ]; then
        echo -e "${GREEN}✓${NC} KafkaUser is Ready"
    else
        echo -e "${YELLOW}!${NC} KafkaUser is not Ready yet"
    fi

    # Check user secret
    if oc get secret "$USER_NAME" -n "$NAMESPACE" &> /dev/null; then
        echo -e "${GREEN}✓${NC} User certificate secret exists"

        # Display user cert info
        USER_CERT=$(oc get secret "$USER_NAME" -n "$NAMESPACE" -o jsonpath='{.data.user\.crt}' | base64 -d)
        echo "$USER_CERT" | openssl x509 -noout -subject -dates
    else
        echo -e "${RED}✗${NC} User certificate secret not found"
    fi
else
    echo -e "${YELLOW}!${NC} KafkaUser '$USER_NAME' does not exist"
fi
echo ""

# Test TLS connectivity
if [ -n "$BOOTSTRAP_SERVER" ]; then
    echo "Testing TLS connectivity..."
    BOOTSTRAP_HOST=$(echo "$BOOTSTRAP_SERVER" | cut -d':' -f1)
    BOOTSTRAP_PORT=$(echo "$BOOTSTRAP_SERVER" | cut -d':' -f2)

    if timeout 5 openssl s_client -connect "$BOOTSTRAP_HOST:$BOOTSTRAP_PORT" -showcerts </dev/null 2>/dev/null | grep -q "Verify return code"; then
        echo -e "${GREEN}✓${NC} TLS connection successful to $BOOTSTRAP_HOST:$BOOTSTRAP_PORT"
    else
        echo -e "${RED}✗${NC} Failed to establish TLS connection"
    fi
fi
echo ""

# Summary
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Extract client certificates:"
echo "   cd client-config && ./extract-certificates.sh"
echo ""
echo "2. Test connection with Kafka client:"
echo "   kafka-console-producer.sh --bootstrap-server $BOOTSTRAP_SERVER \\"
echo "     --topic test-topic --producer.config client.properties"
echo ""
echo "3. Check logs if there are issues:"
echo "   oc logs ${CLUSTER_NAME}-kafka-0 -n $NAMESPACE"
echo ""
