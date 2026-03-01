# Mathematical Formulations

## Quantum Variational Algorithms

This document provides comprehensive mathematical formulations for all quantum algorithms implemented in the QSOP platform.

---

## Table of Contents

1. [QAOA - Quantum Approximate Optimization Algorithm](#qaoa---quantum-approximate-optimization-algorithm)
2. [VQE - Variational Quantum Eigensolver](#vqe---variational-quantum-eigensolver)
3. [Grover's Algorithm](#grovers-algorithm)
4. [Quantum Fourier Transform (QFT)](#quantum-fourier-transform-qft)
5. [Quantum Phase Estimation (QPE)](#quantum-phase-estimation-qpe)
6. [Error Mitigation](#error-mitigation)
7. [Quantum Gradients](#quantum-gradients)

---

## QAOA - Quantum Approximate Optimization Algorithm

### Problem Formulation

QAOA is designed for solving combinatorial optimization problems. Given a cost function $C(z)$ where $z \in \{0, 1\}^n$, we seek to find:

$$
z^* = \arg\min_{z \in \{0,1\}^n} C(z)
$$

### Hamiltonian Encoding

We map the classical cost function to a quantum Hamiltonian $\hat{H}_C$ such that:

$$
\hat{H}_C |z\rangle = C(z) |z\rangle
$$

For **MaxCut** problem on graph $G = (V, E)$ with edge weights $w_{ij}$:

$$
\hat{H}_C = \sum_{(i,j) \in E} \frac{w_{ij}}{2} (1 - \sigma_i^z \sigma_j^z)
$$

where $\sigma_i^z \in \{+1, -1\}$ is the Pauli-Z operator on qubit $i$.

For **QUBO** (Quadratic Unconstrained Binary Optimization) with objective:

$$
C(z) = \sum_i Q_{ii} z_i + \sum_{i<j} Q_{ij} z_i z_j + \text{const}
$$

The Hamiltonian becomes:

$$
\hat{H}_C = \sum_i Q_{ii} \frac{1 - \sigma_i^z}{2} + \sum_{i<j} Q_{ij} \frac{1 - \sigma_i^z}{2} \frac{1 - \sigma_j^z}{2}
$$

### Mixer Hamiltonian

The mixer $\hat{H}_M$ drives transitions between computational basis states. Common choices:

1. **X-mixer** (transverse field):
   $$
   \hat{H}_M = \sum_i \sigma_i^x
   $$

2. **XY-mixer** (for constrained problems):
   $$
   \hat{H}_M = \sum_{\langle i, j \rangle} (\sigma_i^x \sigma_j^x + \sigma_i^y \sigma_j^y)
   $$

3. **Grover-mixer** (for amplitude amplification):
   $$
   \hat{H}_G = 2|s^+\rangle\langle s^+| - \mathbb{I}, \quad |s^+\rangle = H^{\otimes n}|0\rangle^{\otimes n}
   $$

### QAOA Ansatz

For depth $p$, the QAOA state is:

$$
|\psi(\vec{\gamma}, \vec{\beta})\rangle = \prod_{k=1}^p e^{-i\beta_k \hat{H}_M} e^{-i\gamma_k \hat{H}_C} |\psi_0\rangle
$$

where:
- $\vec{\gamma} = (\gamma_1, \gamma_2, \ldots, \gamma_p)$ are problem unitary parameters
- $\vec{\beta} = (\beta_1, \beta_2, \ldots, \beta_p)$ are mixer unitary parameters
- $|\psi_0\rangle = H^{\otimes n}|0\rangle^{\otimes n}$ is the uniform superposition initialization

### Objective Function

The optimization objective is the expected value of the cost Hamiltonian:

$$
f(\vec{\gamma}, \vec{\beta}) = \langle \psi(\vec{\gamma}, \vec{\beta}) | \hat{H}_C | \psi(\vec{\gamma}, \vec{\beta}) \rangle
$$

We seek to minimize this expectation:

$$
(\vec{\gamma}^*, \vec{\beta}^*) = \arg\min_{\vec{\gamma}, \vec{\beta}} f(\vec{\gamma}, \vec{\beta})
$$

### Measurement

After measuring the final state in the computational basis, we obtain samples $z_1, z_2, \ldots, z_m$ with $m$ shots. The expectation value is estimated as:

$$
\hat{f}(\vec{\gamma}, \vec{\beta}) = \frac{1}{m} \sum_{i=1}^m C(z_i)
$$

### Approximation Ratio

For MaxCut, the approximation ratio $\alpha$ is:

$$
\alpha = \frac{E[z_{\text{QAOA}}]}{z_{\text{OPT}}}
$$

where:
- $z_{\text{OPT}}$ is the optimal MaxCut value
- $E[z_{\text{QAOA}}] = \frac{1}{m} \sum_{i=1}^m C(z_i)$ is the expected QAOA value

### Convergence

QAOA converges to the global optimum in the limit $p \to \infty$ (Farhi et al., 2014):

$$
\lim_{p \to \infty} \min_{\vec{\gamma}, \vec{\beta}} f(\vec{\gamma}, \vec{\beta}) = \min_{z \in \{0,1\}^n} C(z)
$$

---

## VQE - Variational Quantum Eigensolver

### Problem Formulation

VQE finds the ground state energy of a Hamiltonian $\hat{H}$:

$$
E_0 = \min_{|\psi\rangle} \frac{\langle \psi | \hat{H} | \psi \rangle}{\langle | \psi \rangle}
$$

### Variational Principle

For any state $|\psi(\vec{\theta})\rangle$ parameterized by $\vec{\theta}$:

$$
\langle \psi(\vec{\theta}) | \hat{H} | \psi(\vec{\theta}) \rangle \geq E_0
$$

with equality if $|\psi(\vec{\theta})\rangle = |E_0\rangle$.

### Hamiltonian Decomposition

We decompose the Hamiltonian into Pauli strings:

$$
\hat{H} = \sum_{j=1}^M \alpha_j P_j, \quad P_j \in \{I, X, Y, Z\}^{\otimes n}
$$

where $\alpha_j$ are real coefficients and $P_j$ are Pauli operators.

### Variational Ansatz

1. **RY Ansatz**:
   $$
   |\psi(\vec{\theta})\rangle = \prod_{k=1}^d \left[ \prod_{i=1}^n R_y(\theta_{i,k}) \right] |\psi_0\rangle
   $$
   where $d$ is the depth and $|\psi_0\rangle$ is a reference state.

2. **RY-RZ Ansatz**:
   $$
   |\psi(\vec{\theta})\rangle = \prod_{k=1}^d \left[ \prod_{i=1}^n R_z(\theta^{(1)}_{i,k}) R_y(\theta^{(2)}_{i,k}) \right] |\psi_0\rangle
   $$

3. **Hardware-Efficient Ansatz**:
   $$
   |\psi(\vec{\theta})\rangle = \prod_{k=1}^d \left[ U_\text{ent} \prod_{i=1}^n R_i(\theta_{i,k}) \right] |\psi_0\rangle
   $$
   where $U_\text{ent}$ provides entanglement between qubits.

4. **UCCSD Ansatz** (Unitary Coupled Cluster Singles and Doubles):
   $$
   |\psi(\vec{\theta})\rangle = e^{\hat{T}(\vec{\theta}) - \hat{T}^\dagger(\vec{\theta})} |HF\rangle
   $$
   where:
   - $|HF\rangle$ is the Hartree-Fock reference state
   - $\hat{T}(\vec{\theta}) = \sum_{i,a} t_{i \to a} a^\dagger_a a_i + \sum_{i<j, a<b} t_{ij \to ab} a^\dagger_a a^\dagger_b a_j a_i$
   - $i,j$ are occupied orbitals, $a,b$ are virtual orbitals

   The excitation operators create the singles and double excitations:
   $$a^\dagger_a a_i$$ - Single excitation
   $$a^\dagger_a a^\dagger_b a_j a_i$$ - Double excitation

### Expectation Value Estimation

The expectation value decomposes as:

$$
E(\vec{\theta}) = \langle \psi(\vec{\theta}) | \hat{H} | \psi(\vec{\theta}) \rangle = \sum_{j=1}^M \alpha_j \langle \psi(\vec{\theta}) | P_j | \psi(\vec{\theta}) \rangle
$$

Each term $\langle P_j \rangle$ can be measured separately:

$$
\langle \psi(\vec{\theta}) | P_j | \psi(\vec{\theta}) \rangle = \sum_{k} p_k \lambda_j(k)
$$

where $p_k = |\langle k | \psi(\vec{\theta}) \rangle|^2$ and $\lambda_j(k)$ is the eigenvalue of $P_j$ for state $|k\rangle$.

### Measurement Grouping

Commuting Pauli terms can be measured in the same basis to reduce circuit executions. The number of distinct measurement bases is at most $4^n$.

### Energy Convergence

VQE converges to the ground state energy:

$$
\lim_{d \to \infty} \min_{\vec{\theta}} E(\vec{\theta}) = E_0
$$

For UCCSD with full singles and doubles excitations, the ansatz is exact for a given orbital basis.

### Chemical Accuracy

A key benchmark is achieving chemical accuracy (1.6 mHa) relative to the true ground state energy:

$$
|E(\vec{\theta}^*) - E_\text{FCI}| < 1.6 \text{ mHa}
$$

where $E_\text{FCI}$ is the Full Configuration Interaction result.

---

## Grover's Algorithm

### Problem Statement

Given an unstructured database of $N = 2^n$ items and a boolean oracle $f: \{0,1\}^n \to \{0,1\}$ that marks solution(s), find $x^*$ such that $f(x^*) = 1$.

### Oracle Representation

The oracle flips the phase of marked states:

$$
U_f |x\rangle = (-1)^{f(x)} |x\rangle = \begin{cases} -|x\rangle & \text{if } f(x) = 1 \\ |x\rangle & \text{if } f(x) = 0 \end{cases}
$$

### Diffusion Operator

The diffusion/inversion-about-average operator:

$$
U_s = 2|s\rangle\langle s| - \mathbb{I}, \quad |s\rangle = H^{\otimes n}|0\rangle^{\otimes n}
$$

In matrix form:
$$
U_s = \frac{2}{N} \sum_{x,y} |x\rangle\langle y| - \mathbb{I}
$$

### Grover Iteration

A single Grover iteration:
$$
G = U_s \cdot U_f
$$

### Amplitude Amplification

After superposition, the system state is:
$$
|\psi_0\rangle = \frac{1}{\sqrt{N}} \sum_{x=0}^{N-1} |x\rangle = \sin(\theta) |\text{bad}\rangle + \cos(\theta) |\text{good}\rangle
$$

where $M$ items are solutions and $\sin(\theta) = \sqrt{M/N}$.

After $t$ Grover iterations:
$$
|\psi_t\rangle = \sin((2t+1)\theta) |\text{bad}\rangle + \cos((2t+1)\theta) |\text{good}\rangle
$$

### Optimal Iterations

For $M \geq 1$ solutions, the optimal number of iterations:
$$
t_{\text{opt}} = \left\lfloor \frac{\pi}{4} \sqrt{\frac{N}{M}} \right\rfloor
$$

### Quantum Advantage

Classical search requires $O(N/M)$ queries on average, while Grover's algorithm requires:
$$
O\left(\sqrt{\frac{N}{M}}\right)
$$

achieving quadratic speedup.

### Success Probability

The probability of measuring a solution after $t$ iterations:
$$
P_{\text{success}}(t) = \sin^2\left((2t+1)\arcsin\left(\sqrt{\frac{M}{N}}\right)\right)
$$

### Threshold-Based Optimization

For optimization with unknown threshold $T$, we iteratively search:
1. Estimate threshold distribution
2. Mark solutions achieving $\geq T$
3. Apply Grover's iteration
4. Update threshold and repeat

---

## Quantum Fourier Transform (QFT)

### Definition

The Quantum Fourier Transform maps basis states to Fourier basis:

$$
\text{QFT}_N |x\rangle = \frac{1}{\sqrt{N}} \sum_{k=0}^{N-1} e^{2\pi i x k / N} |k\rangle
$$

where $N = 2^n$ and $x, k \in \{0, 1, \ldots, N-1\}$.

### Circuit Construction

For $n$ qubits, QFT applies:
$$
\text{QFT}|x_1 x_2 \ldots x_n\rangle = \frac{1}{2^{n/2}} \bigotimes_{j=1}^n \left(|0\rangle + e^{2\pi i 0.x_j x_{j+1} \ldots x_n} |1\rangle\right)
$$

with $0.x_j x_{j+1} \ldots x_n = \sum_{k=j}^n x_k / 2^{k-j+1}$.

### Controlled Phase Gates

QFT uses controlled rotation gates:
$$
\text{CR}_k |t\rangle |c\rangle = \begin{cases} |t\rangle |c\rangle & \text{if } c = 0 \\ e^{2\pi i / 2^k} |t\rangle |c\rangle & \text{if } c = 1 \end{cases}
$$

### Circuit Depth

QFT requires $O(n^2)$ gates:
- $n$ Hadamard gates
- $\frac{n(n-1)}{2}$ controlled rotation gates
- $\frac{n}{2}$ swap gates for bit reversal

### Inverse QFT

The inverse QFT is:
$$
\text{QFT}^\dagger_N |x\rangle = \frac{1}{\sqrt{N}} \sum_{k=0}^{N-1} e^{-2\pi i x k / N} |k\rangle
$$

Implemented by reversing the QFT circuit and negating rotation angles.

---

## Quantum Phase Estimation

### Problem Statement

Given a unitary operator $\hat{U}$ with eigenstate $|\psi\rangle$:

$$
\hat{U} |\psi\rangle = e^{2\pi i \phi} |\psi\rangle
$$

estimate the phase $\phi \in [0, 1)$ to $n$ bits of precision.

### Precision Qubits

The phase is encoded in $n$ precision qubits:
$$
|k\rangle = \frac{1}{2^{n/2}} \sum_{j=0}^{2^n-1} \frac{e^{2\pi i j k / 2^n}}{2^n} |j\rangle
$$

### Controlled Unitaries

Apply controlled-$\hat{U}^{2^k}$ gates for $k = 0, 1, \ldots, n-1$:
$$
\frac{1}{2^n} \sum_{j=0}^{2^n-1} |j\rangle \bigotimes_{k=0}^{n-1} \hat{U}^{2^k j_k} |\psi\rangle = \frac{1}{2^n} \sum_{j=0}^{2^n-1} e^{2\pi i \phi j} |j\rangle |\psi\rangle
$$

### Inverse QFT

Apply $\text{QFT}^\dagger$ to extract phase:
$$
\text{QFT}^\dagger \frac{1}{2^n} \sum_{j=0}^{2^n-1} e^{2\pi i \phi j} |j\rangle = \left\lfloor 2^n \phi \right\rceil_{2^n} \rangle
$$

where $\lfloor x \rceil_{2^n}$ rounds $x$ to the nearest multiple of $1/2^n$.

### Phase Extraction

After measurement, obtain binary representation:
$$
|j_1 j_2 \ldots j_n\rangle \Rightarrow \phi_{\text{est}} = 0.j_1 j_2 \ldots j_n = \sum_{k=1}^n \frac{j_k}{2^k}
$$

### Precision

The error is bounded by:
$$
|\phi_{\text{est}} - \phi| < \frac{1}{2^n}
$$

---

## Error Mitigation

### Zero-Noise Extrapolation (ZNE)

**Principle:** Execute circuits at scaled noise levels $\{1, \lambda_2, \lambda_3, \ldots\}$ and extrapolate to $\lambda = 0$.

**Noise Scaling:**
- Gate folding: Replace each gate $G$ with $GG^\dagger G$
- Unitary folding: Replace circuit $U$ with $UU^\dagger U$

**Extrapolation Methods:**

1. **Linear:**
   $$E(0) = \frac{\lambda_2 E(1) - \lambda_1 E(\lambda_2)}{\lambda_2 - \lambda_1}$$

2. **Richardson:**
   $$E(0) = \sum_{j=0}^{m} c_j E(\lambda_j)$$
   where coefficients $c_j$ depend on the chosen Richardson scheme.

3. **Exponential:**
   $$E(\lambda) = A + B e^{-c\lambda} \Rightarrow E(0) = \lim_{\lambda \to 0} E(\lambda) = A$$

### Readout Error Mitigation

**Calibration Matrix:**
For $n$ qubits, construct $2^n \times 2^n$ confusion matrix $M$ where:
$$M_{j,i} = P(\text{measure } j | \text{prepare } i)$$

**Inversion:**
The true probability vector $p_{\text{true}}$ and observed $p_{\text{obs}}$ satisfy:
$$p_{\text{obs}} = M \cdot p_{\text{true}}$$

Thus:
$$p_{\text{true}} = M^{-1} \cdot p_{\text{obs}}$$

Regularized inversion with Tikhonov regularization:
$$M^{-1} = (M^T M + \lambda \mathbb{I})^{-1} M^T$$

### Virtual Distillation

For $m$ copies of density matrix $\rho$, the distilled state:
$$\rho_m = \frac{\rho^{\otimes m}}{\text{Tr}(\rho^{\otimes m})}$$

The expectation value:
$$\langle O \rangle_m = \frac{\text{Tr}(\rho^{\otimes m} O^{\otimes m})}{\text{Tr}(\rho^{\otimes m})}$$

---

## Quantum Gradients

### Parameter Shift Rule

For circuits composed of Pauli rotations $R_j(\theta) = e^{-i\theta P_j/2}$ where $P_j \in \{X, Y, Z\}$:

$$\frac{\partial}{\partial \theta_j} \langle O \rangle = \frac{\langle O(\theta_j + s) \rangle - \langle O(\theta_j - s) \rangle}{2}$$

where $s = \pi/2$ is the optimal shift.

**Proof:**
$$\langle O(\theta_j) \rangle = \bra{\psi(\theta)} O \ket{\psi(\theta)}$$

Using the identity for Pauli rotations:
$$R_j(\theta_j + s) - R_j(\theta_j - s) = 2i \sin(s) P_j R_j(\theta_j)$$

For $s = \pi/2$:
$$\frac{R_j(\theta_j + \pi/2) - R_j(\theta_j - \pi/2)}{2i} = P_j R_j(\theta_j)$$

Thus the derivative reduces to:
$$\frac{\partial}{\partial \theta_j} \langle O \rangle = \langle \bra{\psi_{-}} O \ket{\psi_+} - \bra{\psi_+} O \ket{\psi_{-}} \rangle$$

which gives the parameter shift rule.

### SPSA Gradient

**Simultaneous Perturbation:** All gradient components estimated with only 2 circuit evaluations per iteration.

**Perturbation Vector:**
$$\Delta = [\Delta_1, \Delta_2, \ldots, \Delta_n]^T, \quad \Delta_j \in \{-1, +1\}$$

**Gradient Estimate:**
$$\hat{g}_j = \frac{O(\theta + c_k \Delta) - O(\theta - c_k \Delta)}{2c_k \Delta_j}$$

where $c_k = c / (k+1)^\gamma$ is the decreasing perturbation magnitude.

**Advantages:**
- $O(1)$ circuit evaluations regardless of parameter count
- Robust to noise
- Suitable for high-dimensional optimization

---

## References

1. Farhi, E., et al. "Quantum Approximate Optimization Algorithm and its Application to Combinatorial Problems." arXiv:1411.4028 (2014).
2. Peruzzo, A., et al. "A variational eigenvalue solver on a photonic quantum processor." Nature Communications 5, 4213 (2014).
3. Grover, L. K. "A fast quantum mechanical algorithm for database search." Proceedings of STOC (1996).
4. Kandala, A., et al. "Error mitigation extends the computational reach of a noisy quantum processor." Nature 567, 761. (2019).
5. Mari, A., et al. "Evaluating analytic gradients on quantum hardware." Physical Review Research 3, 013314 (2021).
6. Temme, K., et al. "Error mitigation for short-depth quantum circuits." Physical Review Letters 119, 180509 (2017).
7. Spall, J. C. "Introduction to Stochastic Search and Optimization." Wiley (2003).
