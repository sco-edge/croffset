import numpy as np

def jain(shares):
    dividend = np.sum(shares)**2
    divisor = shares.size * np.sum(shares**2)
    return dividend / divisor

encap_fq = np.array([21.4, 15.1, 13.8, 9.13, 9.12, 21.2])
encap_fq_codel = np.array([17.3, 9.43, 9.43, 17.7, 17.7, 17.8])
host_fq = np.array([18.1, 18.4, 18.5, 18.7, 9.96, 9.55])
host_fq_codel = np.array([12.2, 12.1, 21.6, 12.1, 23.6, 12.2])

print(f"Encapsulation-FQ: {jain(encap_fq):.3f}")
print(f"Encapsulation-FQ-CoDel: {jain(encap_fq_codel):.3f}")
print(f"Host-FQ: {jain(host_fq):.3f}")
print(f"Host-FQ-CoDel: {jain(host_fq_codel):.3f}")