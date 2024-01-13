#!/bin/bash

kubectl get pods -A | awk '/neper-client/ { print $2 }' | xargs kubectl delete pod
kubectl get deploy -A | awk '/neper-server-deployment/ { print $2 }' | xargs kubectl delete deploy