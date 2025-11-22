#!/bin/bash
# Test script for NRF BLE API

echo "=== Testing NRF BLE API ==="
echo ""

# Get your Pi's IP address
PI_IP="localhost"  # Change to your actual Pi IP if testing from another device

echo "1. Check API status"
curl http://$PI_IP:5000/status
echo -e "\n"

echo "2. Connect to BLE device"
curl -X POST http://$PI_IP:5000/connect
echo -e "\n"

echo "3. Send Move Up command"
curl -X POST http://$PI_IP:5000/move \
  -H "Content-Type: application/json" \
  -d '{"target_id": "01", "direction": "Up"}'
echo -e "\n"

sleep 2

echo "4. Send Move Down command"
curl -X POST http://$PI_IP:5000/move \
  -H "Content-Type: application/json" \
  -d '{"target_id": "01", "direction": "Down"}'
echo -e "\n"

echo "5. Check connection status"
curl http://$PI_IP:5000/status
echo -e "\n"

echo "6. Disconnect"
curl -X POST http://$PI_IP:5000/disconnect
echo -e "\n"

echo "=== Test Complete ==="
