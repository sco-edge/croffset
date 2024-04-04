#!/bin/bash

cat neper.yaml | sed -s "s/{CROFFSET_CLIENT}/$2/g; s/{CROFFSET_SERVER}/$3/g" | kubectl --kubeconfig /home/$1/.kube/config apply -f -