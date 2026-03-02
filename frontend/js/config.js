const CONFIG = {
    apiUrl: 'http://localhost:8001/api/v1',
    apiBase: 'http://localhost:8001/api/v1',
    healthUrl: 'http://localhost:8001',
    debug: true
};

// Test backend connectivity
async function testBackendConnection() {
    try {
        console.log('Testing backend connection to:', CONFIG.healthUrl);
        const response = await fetch(`${CONFIG.healthUrl}/health`);
        const data = await response.json();
        console.log('✓ Backend connected:', data);
        return true;
    } catch (error) {
        console.error('✗ Backend connection failed:', error);
        return false;
    }
}

// Export for use in other scripts
window.CONFIG = CONFIG;
window.testBackendConnection = testBackendConnection;

console.log('✓ Config loaded:', CONFIG);
