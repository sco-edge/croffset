Compensating RTT Offsets in Container Networking
=============
A measurement tool to measure the RTT offset of various container networking based on ePPing.

Use `-V` option to track VXLAN-encapsulated flows from conatiner overlay networks.

TODO: Integrating the modified ePPing with tcprtt

Caveat: The current version measures RTTs when the frames arrive at the host's NIC because it is attached to the xdp hook, which is not the end goal of measuring RTT offsets in container networks. The accurate measurement is under development.
