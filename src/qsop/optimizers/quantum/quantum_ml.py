"""
Quantum Machine Learning Integration Module.

Provides quantum-enhanced machine learning capabilities including
quantum neural networks, quantum feature mapping, and hybrid
quantum-classical models.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from numpy.typing import NDArray

logger = logging.getLogger(__name__)


class QMLModelType(Enum):
    """Types of quantum machine learning models."""
    QUANTUM_NEURAL_NETWORK = "quantum_neural_network"
    VARIATIONAL_CLASSIFIER = "variational_classifier"
    QUANTUM_KERNEL = "quantum_kernel"
    QUANTUM_GENERATIVE_MODEL = "quantum_generative_model"
    HYBRID_MODEL = "hybrid_model"


class FeatureMapType(Enum):
    """Types of quantum feature maps."""
    PAULI = "pauli"
    ZZ = "zz"
    AMPLITUDE = "amplitude"
    CUSTOM = "custom"


@dataclass
class QMLModelConfig:
    """Configuration for quantum ML models."""
    
    model_type: QMLModelType
    num_qubits: int
    num_layers: int = 2
    feature_map_type: FeatureMapType = FeatureMapType.PAULI
    optimizer: str = "COBYLA"
    shots: int = 1000
    learning_rate: float = 0.01
    max_iterations: int = 100
    batch_size: int = 32
    
    # Hybrid model parameters
    classical_layers: List[int] = field(default_factory=lambda: [64, 32])
    activation: str = "relu"
    
    # Regularization
    dropout: float = 0.1
    l2_regularization: float = 0.01
    
    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> "QMLModelConfig":
        """Create configuration from dictionary."""
        return cls(
            model_type=QMLModelType(config.get("model_type", "quantum_neural_network")),
            num_qubits=config.get("num_qubits", 4),
            num_layers=config.get("num_layers", 2),
            feature_map_type=FeatureMapType(config.get("feature_map_type", "pauli")),
            optimizer=config.get("optimizer", "COBYLA"),
            shots=config.get("shots", 1000),
            learning_rate=config.get("learning_rate", 0.01),
            max_iterations=config.get("max_iterations", 100),
            batch_size=config.get("batch_size", 32),
            classical_layers=config.get("classical_layers", [64, 32]),
            activation=config.get("activation", "relu"),
            dropout=config.get("dropout", 0.1),
            l2_regularization=config.get("l2_regularization", 0.01),
        )


class QuantumFeatureMap:
    """Quantum feature mapping for classical data."""
    
    def __init__(
        self,
        num_qubits: int,
        feature_map_type: FeatureMapType = FeatureMapType.PAULI,
        num_features: Optional[int] = None
    ):
        self.num_qubits = num_qubits
        self.feature_map_type = feature_map_type
        self.num_features = num_features or num_qubits
        
        # Initialize feature map parameters
        self._parameters = np.random.uniform(0, 2 * np.pi, size=self._get_parameter_count())
    
    def _get_parameter_count(self) -> int:
        """Get number of trainable parameters."""
        if self.feature_map_type == FeatureMapType.PAULI:
            return self.num_qubits * 2
        elif self.feature_map_type == FeatureMapType.ZZ:
            return self.num_qubits * 2 + self.num_qubits * (self.num_qubits - 1) // 2
        elif self.feature_map_type == FeatureMapType.AMPLITUDE:
            return self.num_qubits
        else:
            return self.num_qubits * 2
    
    def encode(self, features: NDArray) -> NDArray:
        """Encode classical features into quantum state.
        
        Args:
            features: Classical feature vector
            
        Returns:
            Encoded quantum state parameters
        """
        if len(features) != self.num_features:
            raise ValueError(f"Expected {self.num_features} features, got {len(features)}")
        
        # Normalize features to [0, 2π]
        normalized_features = self._normalize_features(features)
        
        # Apply feature map encoding
        if self.feature_map_type == FeatureMapType.PAULI:
            return self._pauli_encoding(normalized_features)
        elif self.feature_map_type == FeatureMapType.ZZ:
            return self._zz_encoding(normalized_features)
        elif self.feature_map_type == FeatureMapType.AMPLITUDE:
            return self._amplitude_encoding(normalized_features)
        else:
            return self._custom_encoding(normalized_features)
    
    def _normalize_features(self, features: NDArray) -> NDArray:
        """Normalize features to [0, 2π]."""
        # Min-max normalization
        min_val = np.min(features)
        max_val = np.max(features)
        
        if max_val == min_val:
            return np.zeros_like(features)
        
        normalized = (features - min_val) / (max_val - min_val)
        return normalized * 2 * np.pi
    
    def _pauli_encoding(self, features: NDArray) -> NDArray:
        """Pauli feature map encoding."""
        encoded = np.zeros(2 * self.num_qubits)
        
        for i in range(self.num_qubits):
            # Rotation around X axis
            encoded[2 * i] = features[i % len(features)]
            # Rotation around Z axis
            encoded[2 * i + 1] = features[(i + self.num_qubits) % len(features)]
        
        return encoded
    
    def _zz_encoding(self, features: NDArray) -> NDArray:
        """ZZ feature map encoding."""
        param_count = self._get_parameter_count()
        encoded = np.zeros(param_count)
        
        # Single-qubit rotations
        for i in range(self.num_qubits):
            encoded[2 * i] = features[i % len(features)]
            encoded[2 * i + 1] = features[(i + self.num_qubits) % len(features)]
        
        # Two-qubit ZZ interactions
        idx = 2 * self.num_qubits
        for i in range(self.num_qubits):
            for j in range(i + 1, self.num_qubits):
                feature_idx = (i + j + 2 * self.num_qubits) % len(features)
                encoded[idx] = features[feature_idx]
                idx += 1
        
        return encoded
    
    def _amplitude_encoding(self, features: NDArray) -> NDArray:
        """Amplitude encoding."""
        # Normalize features to create probability distribution
        normalized = np.abs(features)
        total = np.sum(normalized)
        
        if total > 0:
            normalized = normalized / total
        
        # Pad or truncate to match number of amplitudes
        num_amplitudes = 2 ** self.num_qubits
        if len(normalized) < num_amplitudes:
            padded = np.zeros(num_amplitudes)
            padded[:len(normalized)] = normalized
            normalized = padded
        else:
            normalized = normalized[:num_amplitudes]
        
        return normalized
    
    def _custom_encoding(self, features: NDArray) -> NDArray:
        """Custom feature map encoding."""
        # Default to Pauli encoding
        return self._pauli_encoding(features)


class QuantumNeuralNetwork:
    """Quantum Neural Network for classification and regression."""
    
    def __init__(self, config: QMLModelConfig):
        self.config = config
        self.feature_map = QuantumFeatureMap(
            config.num_qubits,
            config.feature_map_type
        )
        
        # Initialize variational parameters
        self._variational_params = np.random.uniform(
            0, 2 * np.pi,
            size=config.num_qubits * config.num_layers * 2
        )
        
        # Training state
        self._is_trained = False
        self._training_history: List[Dict[str, float]] = []
    
    def forward(self, features: NDArray) -> NDArray:
        """Forward pass through the quantum neural network.
        
        Args:
            features: Input features
            
        Returns:
            Network output
        """
        # Encode features
        encoded = self.feature_map.encode(features)
        
        # Apply variational layers
        output = self._apply_variational_layers(encoded)
        
        return output
    
    def _apply_variational_layers(self, encoded: NDArray) -> NDArray:
        """Apply variational quantum layers."""
        current_state = encoded.copy()
        
        for layer in range(self.config.num_layers):
            # Apply parameterized rotations
            for qubit in range(self.config.num_qubits):
                param_idx = layer * self.config.num_qubits * 2 + qubit * 2
                rx_param = self._variational_params[param_idx]
                rz_param = self._variational_params[param_idx + 1]
                
                # Apply RX rotation
                current_state[qubit] = self._apply_rotation(
                    current_state[qubit], rx_param, 'X'
                )
                
                # Apply RZ rotation
                current_state[qubit] = self._apply_rotation(
                    current_state[qubit], rz_param, 'Z'
                )
            
            # Apply entangling gates
            current_state = self._apply_entanglement(current_state, layer)
        
        return current_state
    
    def _apply_rotation(self, value: float, angle: float, axis: str) -> float:
        """Apply rotation gate."""
        # Simplified rotation (in real QNN, this would be quantum gates)
        if axis == 'X':
            return value * np.cos(angle) + np.sin(angle)
        elif axis == 'Z':
            return value * np.exp(1j * angle)
        else:
            return value
    
    def _apply_entanglement(self, state: NDArray, layer: int) -> NDArray:
        """Apply entangling gates between qubits."""
        entangled = state.copy()
        
        # Apply CNOT-like entanglement
        for i in range(len(state) - 1):
            entangled[i] = (state[i] + state[i + 1]) / np.sqrt(2)
            entangled[i + 1] = (state[i] - state[i + 1]) / np.sqrt(2)
        
        return entangled
    
    def predict(self, features: NDArray) -> Union[int, float]:
        """Make predictions.
        
        Args:
            features: Input features
            
        Returns:
            Prediction (class label or regression value)
        """
        output = self.forward(features)
        
        # For classification, return class label
        if len(output) > 1:
            return np.argmax(np.abs(output))
        else:
            # For regression, return value
            return np.real(output[0])
    
    def train(
        self,
        X_train: NDArray,
        y_train: NDArray,
        X_val: Optional[NDArray] = None,
        y_val: Optional[NDArray] = None
    ) -> Dict[str, Any]:
        """Train the quantum neural network.
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            
        Returns:
            Training history
        """
        logger.info(f"Training QNN with {len(X_train)} samples")
        
        # Simple gradient descent training
        for iteration in range(self.config.max_iterations):
            # Compute gradients (simplified)
            gradients = self._compute_gradients(X_train, y_train)
            
            # Update parameters
            self._variational_params -= self.config.learning_rate * gradients
            
            # Compute loss
            loss = self._compute_loss(X_train, y_train)
            
            # Record history
            history_entry = {
                "iteration": iteration,
                "loss": loss,
            }
            
            if X_val is not None and y_val is not None:
                val_loss = self._compute_loss(X_val, y_val)
                history_entry["val_loss"] = val_loss
            
            self._training_history.append(history_entry)
            
            # Log progress
            if iteration % 10 == 0:
                logger.info(f"Iteration {iteration}: Loss = {loss:.4f}")
        
        self._is_trained = True
        logger.info("Training completed")
        
        return {
            "history": self._training_history,
            "final_loss": self._training_history[-1]["loss"],
        }
    
    def _compute_gradients(self, X: NDArray, y: NDArray) -> NDArray:
        """Compute gradients (simplified)."""
        # In real QNN, this would use parameter shift rule
        # Here we use a simplified gradient computation
        gradients = np.zeros_like(self._variational_params)
        
        for i in range(len(gradients)):
            # Finite difference approximation
            epsilon = 0.01
            original_param = self._variational_params[i]
            
            # Forward pass with +epsilon
            self._variational_params[i] = original_param + epsilon
            loss_plus = self._compute_loss(X, y)
            
            # Forward pass with -epsilon
            self._variational_params[i] = original_param - epsilon
            loss_minus = self._compute_loss(X, y)
            
            # Restore original parameter
            self._variational_params[i] = original_param
            
            # Compute gradient
            gradients[i] = (loss_plus - loss_minus) / (2 * epsilon)
        
        return gradients
    
    def _compute_loss(self, X: NDArray, y: NDArray) -> float:
        """Compute loss."""
        predictions = np.array([self.predict(x) for x in X])
        
        # Mean squared error for regression
        if len(y.shape) == 1 and y.dtype.kind in 'fc':
            return np.mean((predictions - y) ** 2)
        
        # Cross-entropy for classification
        else:
            # One-hot encode predictions
            num_classes = len(np.unique(y))
            pred_onehot = np.zeros((len(predictions), num_classes))
            for i, pred in enumerate(predictions):
                if 0 <= pred < num_classes:
                    pred_onehot[i, pred] = 1
            
            # Compute cross-entropy
            epsilon = 1e-10
            pred_onehot = np.clip(pred_onehot, epsilon, 1 - epsilon)
            return -np.mean(y * np.log(pred_onehot + epsilon))
    
    def evaluate(self, X_test: NDArray, y_test: NDArray) -> Dict[str, float]:
        """Evaluate the model.
        
        Args:
            X_test: Test features
            y_test: Test labels
            
        Returns:
            Evaluation metrics
        """
        predictions = np.array([self.predict(x) for x in X_test])
        
        # Compute accuracy for classification
        if len(y_test.shape) == 1 and y_test.dtype.kind in 'fc':
            accuracy = np.mean(predictions == y_test)
            return {"accuracy": accuracy}
        
        # Compute MSE for regression
        else:
            mse = np.mean((predictions - y_test) ** 2)
            return {"mse": mse}


class HybridQuantumClassicalModel:
    """Hybrid quantum-classical machine learning model."""
    
    def __init__(self, config: QMLModelConfig):
        self.config = config
        self.qml_model = QuantumNeuralNetwork(config)
        
        # Initialize classical layers (simplified)
        self._classical_weights = []
        input_size = config.num_qubits
        
        for layer_size in config.classical_layers:
            weights = np.random.randn(input_size, layer_size) * 0.1
            self._classical_weights.append(weights)
            input_size = layer_size
        
        # Output layer
        self._output_weights = np.random.randn(input_size, 1) * 0.1
    
    def forward(self, features: NDArray) -> NDArray:
        """Forward pass through hybrid model.
        
        Args:
            features: Input features
            
        Returns:
            Model output
        """
        # Quantum feature encoding
        quantum_output = self.qml_model.forward(features)
        
        # Classical layers
        current = quantum_output
        for weights in self._classical_weights:
            # Linear transformation
            current = np.dot(current, weights)
            
            # Activation
            if self.config.activation == "relu":
                current = np.maximum(0, current)
            elif self.config.activation == "sigmoid":
                current = 1 / (1 + np.exp(-current))
            elif self.config.activation == "tanh":
                current = np.tanh(current)
        
        # Output layer
        output = np.dot(current, self._output_weights)
        
        return output
    
    def predict(self, features: NDArray) -> Union[int, float]:
        """Make predictions."""
        output = self.forward(features)
        
        # Classification
        if output > 0.5:
            return 1
        else:
            return 0
    
    def train(
        self,
        X_train: NDArray,
        y_train: NDArray,
        X_val: Optional[NDArray] = None,
        y_val: Optional[NDArray] = None
    ) -> Dict[str, Any]:
        """Train the hybrid model.
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            
        Returns:
            Training history
        """
        logger.info(f"Training hybrid model with {len(X_train)} samples")
        
        # Train quantum component first
        qml_history = self.qml_model.train(X_train, y_train, X_val, y_val)
        
        # Then train classical layers (simplified)
        for iteration in range(self.config.max_iterations):
            # Compute gradients for classical layers
            gradients = self._compute_classical_gradients(X_train, y_train)
            
            # Update weights
            for i, weights in enumerate(self._classical_weights):
                self._classical_weights[i] -= self.config.learning_rate * gradients[i]
            
            self._output_weights -= self.config.learning_rate * gradients[-1]
        
        logger.info("Hybrid model training completed")
        
        return {
            "qml_history": qml_history,
            "final_loss": qml_history["final_loss"],
        }
    
    def _compute_classical_gradients(self, X: NDArray, y: NDArray) -> List[NDArray]:
        """Compute gradients for classical layers (simplified)."""
        gradients = []
        
        # Initialize gradients
        for weights in self._classical_weights:
            gradients.append(np.zeros_like(weights))
        gradients.append(np.zeros_like(self._output_weights))
        
        # Compute gradients using backpropagation (simplified)
        for i in range(len(X)):
            x = X[i]
            target = y[i]
            
            # Forward pass
            activations = [x]
            current = x
            
            for weights in self._classical_weights:
                current = np.dot(current, weights)
                if self.config.activation == "relu":
                    current = np.maximum(0, current)
                activations.append(current)
            
            output = np.dot(current, self._output_weights)
            
            # Backward pass
            error = output - target
            
            # Output layer gradient
            gradients[-1] += np.outer(activations[-1], error)
            
            # Hidden layer gradients
            for j in range(len(self._classical_weights) - 1, -1, -1):
                error = np.dot(error, self._classical_weights[j].T)
                gradients[j] += np.outer(activations[j], error)
        
        # Average gradients
        batch_size = len(X)
        for i in range(len(gradients)):
            gradients[i] /= batch_size
        
        return gradients
    
    def evaluate(self, X_test: NDArray, y_test: NDArray) -> Dict[str, float]:
        """Evaluate the hybrid model."""
        predictions = np.array([self.predict(x) for x in X_test])
        accuracy = np.mean(predictions == y_test)
        
        return {"accuracy": accuracy}


class QMLModelFactory:
    """Factory for creating quantum ML models."""
    
    @staticmethod
    def create_model(config: Union[QMLModelConfig, Dict[str, Any]]) -> Union[QuantumNeuralNetwork, HybridQuantumClassicalModel]:
        """Create a quantum ML model.
        
        Args:
            config: Model configuration
            
        Returns:
            Quantum ML model instance
        """
        if isinstance(config, dict):
            config = QMLModelConfig.from_dict(config)
        
        if config.model_type == QMLModelType.QUANTUM_NEURAL_NETWORK:
            return QuantumNeuralNetwork(config)
        elif config.model_type == QMLModelType.HYBRID_MODEL:
            return HybridQuantumClassicalModel(config)
        else:
            raise ValueError(f"Unsupported model type: {config.model_type}")


# Utility functions
def create_qml_config(
    model_type: str = "quantum_neural_network",
    num_qubits: int = 4,
    **kwargs
) -> QMLModelConfig:
    """Create a QML model configuration.
    
    Args:
        model_type: Type of model
        num_qubits: Number of qubits
        **kwargs: Additional configuration parameters
        
    Returns:
        Model configuration
    """
    config_dict = {
        "model_type": model_type,
        "num_qubits": num_qubits,
        **kwargs
    }
    return QMLModelConfig.from_dict(config_dict)