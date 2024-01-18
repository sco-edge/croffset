#!/bin/bash

kubectl get pods -A | awk '/iperf-client/ { print $2 }' | xargs kubectl delete pod
kubectl get deploy -A | awk '/iperf-server-deployment/ { print $2 }' | xargs kubectl delete deploy