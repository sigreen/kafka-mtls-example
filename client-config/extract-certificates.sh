#!/bin/bash
# Script to extract Kafka client certificates from OpenShift secrets
# Run this script after creating the KafkaUser resource

set -e

NAMESPACE="kafka"
CLUSTER_NAME="my-cluster"
USER_NAME="external-client"
OUTPUT_DIR="./certs"

echo "Extracting certificates for Kafka client authentication..."

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Extract cluster CA certificate (truststore)
echo "Extracting cluster CA certificate..."
oc get secret "${CLUSTER_NAME}-cluster-ca-cert" -n "$NAMESPACE" -o jsonpath='{.data.ca\.p12}' | base64 -d > "$OUTPUT_DIR/truststore.p12"
oc get secret "${CLUSTER_NAME}-cluster-ca-cert" -n "$NAMESPACE" -o jsonpath='{.data.ca\.password}' | base64 -d > "$OUTPUT_DIR/truststore.password"

echo "Truststore password: $(cat $OUTPUT_DIR/truststore.password)"

# Extract user certificate and key (keystore)
echo "Extracting user certificate and key..."
oc get secret "$USER_NAME" -n "$NAMESPACE" -o jsonpath='{.data.user\.p12}' | base64 -d > "$OUTPUT_DIR/user.p12"
oc get secret "$USER_NAME" -n "$NAMESPACE" -o jsonpath='{.data.user\.password}' | base64 -d > "$OUTPUT_DIR/user.password"

echo "Keystore password: $(cat $OUTPUT_DIR/user.password)"

# Also extract PEM format for other tools
echo "Extracting PEM format certificates..."
oc get secret "$USER_NAME" -n "$NAMESPACE" -o jsonpath='{.data.user\.crt}' | base64 -d > "$OUTPUT_DIR/user.crt"
oc get secret "$USER_NAME" -n "$NAMESPACE" -o jsonpath='{.data.user\.key}' | base64 -d > "$OUTPUT_DIR/user.key"
oc get secret "${CLUSTER_NAME}-cluster-ca-cert" -n "$NAMESPACE" -o jsonpath='{.data.ca\.crt}' | base64 -d > "$OUTPUT_DIR/ca.crt"

# Get bootstrap server address
echo "Getting bootstrap server address..."
BOOTSTRAP_SERVER=$(oc get kafka "$CLUSTER_NAME" -n "$NAMESPACE" -o jsonpath='{.status.listeners[?(@.name=="external")].bootstrapServers}')

echo ""
echo "=========================================="
echo "Certificate extraction complete!"
echo "=========================================="
echo ""
echo "Files created in $OUTPUT_DIR:"
echo "  - truststore.p12 (cluster CA)"
echo "  - user.p12 (client certificate and key)"
echo "  - ca.crt, user.crt, user.key (PEM format)"
echo ""
echo "Bootstrap server: $BOOTSTRAP_SERVER"
echo ""
echo "Update your client.properties with:"
echo "  ssl.truststore.location=$OUTPUT_DIR/truststore.p12"
echo "  ssl.truststore.password=$(cat $OUTPUT_DIR/truststore.password)"
echo "  ssl.keystore.location=$OUTPUT_DIR/user.p12"
echo "  ssl.keystore.password=$(cat $OUTPUT_DIR/user.password)"
echo ""
