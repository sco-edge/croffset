#!/bin/bash

cat iperf3.yaml | sed -s "s/{NODE}/$2/g" | kubectl --kubeconfig /home/$1/.kube/config apply -f -