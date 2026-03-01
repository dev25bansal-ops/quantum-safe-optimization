/**
 * Unit Tests for Component System
 * Tests for Component base class, ToastContainer, Modal, and ModalManager
 */

// Since we don't have a Node.js test environment set up, 
// these tests are designed to be run in the browser console
// or in a simple test runner.

export class ComponentTestSuite {
    constructor() {
        this.tests = [];
        this.passed = 0;
        this.failed = 0;
        this.results = [];
    }

    test(name, fn) {
        this.tests.push({ name, fn });
    }

    async run() {
        console.log('🧪 Running Component Tests...\n');
        
        for (const test of this.tests) {
            try {
                await test.fn();
                this.passed++;
                this.results.push({ name: test.name, status: 'pass' });
                console.log(`✅ ${test.name}`);
            } catch (error) {
                this.failed++;
                this.results.push({ name: test.name, status: 'fail', error: error.message });
                console.log(`❌ ${test.name}`);
                console.error(`   ${error.message}`);
            }
        }

        console.log(`\n${'='.repeat(60)}`);
        console.log(`Tests: ${this.passed} passed, ${this.failed} failed`);
        console.log(`${'='.repeat(60)}`);

        return {
            total: this.tests.length,
            passed: this.passed,
            failed: this.failed,
            results: this.results
        };
    }

    assert(condition, message) {
        if (!condition) {
            throw new Error(message || 'Assertion failed');
        }
    }

    assertEquals(actual, expected, message) {
        if (actual !== expected) {
            throw new Error(message || `Expected ${expected}, got ${actual}`);
        }
    }
}

// Test suite implementation
export function createComponentTests() {
    const suite = new ComponentTestSuite();

    // Component base class tests
    suite.test('Component: should initialize with default state', async () => {
        const Component = (window.Component || {}).default;
        suite.assert(Component !== undefined, 'Component should be available');
        
        const component = new Component({ test: 'prop' });
        suite.assertEquals(component.props.test, 'prop', 'Props should be set');
        suite.assert(component.state !== undefined, 'State object should exist');
    });

    suite.test('Component: should mount to DOM', async () => {
        const Component = (window.Component || {}).default;
        const component = new Component();
        const container = document.createElement('div');
        
        component.render = () => '<div>Test</div>';
        component.mount(container);
        
        suite.assertEquals(container.innerHTML, '<div>Test</div>', 'Container should contain rendered content');
        suite.assertEquals(component.isMounted, true, 'Component should be mounted');
        suite.assertEquals(component.element, container, 'Element should be set to container');
    });

    suite.test('Component: should update state and trigger render', async () => {
        const Component = (window.Component || {}).default;
        const component = new Component();
        const container = document.createElement('div');
        
        let renderCount = 0;
        component.render = () => {
            renderCount++;
            return `<div>Count: ${renderCount}</div>`;
        };
        
        component.mount(container);
        suite.assertEquals(renderCount, 1, 'Should render once on mount');
        
        component.setState({ test: 'value' });
        suite.assertEquals(renderCount, 2, 'Should render again on state update');
    });

    suite.test('Component: should unmount and cleanup', async () => {
        const Component = (window.Component || {}).default;
        const component = new Component();
        const container = document.createElement('div');
        
        let unmountCalled = false;
        component.componentWillUnmount = () => {
            unmountCalled = true;
        };
        
        component.mount(container);
        component.unmount();
        
        suite.assertEquals(unmountCalled, true, 'componentWillUnmount should be called');
        suite.assertEquals(container.innerHTML, '', 'Container should be cleared');
        suite.assertEquals(component.isMounted, false, 'Component should not be mounted');
    });

    // Modal tests
    suite.test('Modal: should create modal instance', async () => {
        const Modal = (window.Modal || {}).default;
        suite.assert(Modal !== undefined, 'Modal should be available');
        
        const modal = new Modal({
            title: 'Test Modal',
            body: 'Modal body',
            size: 'medium'
        });
        
        suite.assertEquals(modal.state.title, 'Test Modal', 'Title should be set');
        suite.assertEquals(modal.state.size, 'medium', 'Size should be set');
    });

    suite.test('Modal: should open and close', async () => {
        const Modal = (window.Modal || {}).default;
        const modal = new Modal({ title: 'Test' });
        const container = document.createElement('div');
        
        modal.mount(container);
        suite.assertEquals(modal.state.isOpen, false, 'Modal should start closed');
        
        modal.open();
        suite.assertEquals(modal.state.isOpen, true, 'Modal should be open');
        
        modal.close();
        suite.assertEquals(modal.state.isOpen, false, 'Modal should be closed');
    });

    // ModalManager tests
    suite.test('ModalManager: should register and open modal', async () => {
        const modalManager = window.modalManager;
        suite.assert(modalManager !== undefined, 'modalManager should be available');
        
        const modal = modalManager.create('test-modal', {
            title: 'Test',
            body: 'Body'
        });
        
        suite.assert(modal !== undefined, 'Modal should be created');
        suite.assert(modalManager.getModal('test-modal') === modal, 'Modal should be retrievable');
        
        modalManager.open('test-modal');
        suite.assert(modalManager.isOpen('test-modal'), 'Modal should be open');
        
        modalManager.close('test-modal');
        suite.assert(!modalManager.isOpen('test-modal'), 'Modal should be closed');
    });

    suite.test('ModalManager: should open all modals', async () => {
        const modalManager = window.modalManager;
        
        modalManager.create('modal-1', { title: 'Modal 1', body: 'Body 1' });
        modalManager.create('modal-2', { title: 'Modal 2', body: 'Body 2' });
        
        modalManager.open('modal-1');
        modalManager.open('modal-2');
        
        suite.assert(modalManager.isOpen('modal-1'), 'Modal 1 should be open');
        suite.assert(modalManager.isOpen('modal-2'), 'Modal 2 should be open');
        
        modalManager.closeAll();
        
        suite.assert(!modalManager.isOpen('modal-1'), 'Modal 1 should be closed');
        suite.assert(!modalManager.isOpen('modal-2'), 'Modal 2 should be closed');
    });

    // Test helper functions
    suite.test('ModalUtils: alertDialog should work', async () => {
        const alertDialog = window.alertDialog;
        suite.assert(alertDialog !== undefined, 'alertDialog should be available');
        suite.assert(typeof alertDialog === 'function', 'alertDialog should be a function');
        
        // We can't actually test the modal opening without a DOM, so just check it exists
        // The actual modal opening would be integration tested
    });

    suite.test('ModalUtils: confirmDialog should return promise', async () => {
        const confirmDialog = window.confirmDialog;
        suite.assert(confirmDialog !== undefined, 'confirmDialog should be available');
        suite.assert(typeof confirmDialog === 'function', 'confirmDialog should be a function');
        
        // Test that it returns a promise
        const promise = confirmDialog('Test', 'Test message');
        suite.assert(promise instanceof Promise, 'Should return a Promise');
        
        // Clean up - cancel the modal
        const modal = window.modalManager.getModal(/confirm-\d+/);
        if (modal) {
            window.modalManager.closeAll();
        }
    });

    // OptimizationSuggestionCard tests
    suite.test('OptimizationSuggestionCard: should create instance', async () => {
        const OptimizationSuggestionCard = window.OptimizationSuggestionCard;
        suite.assert(OptimizationSuggestionCard !== undefined, 'OptimizationSuggestionCard should be available');
        
        const card = new OptimizationSuggestionCard({
            problemType: 'QAOA',
            backend: 'local_simulator',
            parameters: { layers: 2, optimizer: 'COBYLA' }
        });
        
        suite.assertEquals(card.state.problemType, 'QAOA', 'Problem type should be set');
        suite.assertEquals(card.state.backend, 'local_simulator', 'Backend should be set');
    });

    suite.test('OptimizationSuggestionCard: should generate suggestions', async () => {
        const OptimizationSuggestionCard = window.OptimizationSuggestionCard;
        const card = new OptimizationSuggestionCard({
            problemType: 'QAOA',
            backend: 'local_simulator',
            parameters: { layers: 1, optimizer: 'COBYLA' }
        });
        
        const container = document.createElement('div');
        card.mount(container);
        
        // Wait a moment for suggestions to be generated
        await new Promise(resolve => setTimeout(resolve, 100));
        
        // Check that suggestions were generated
        const suggestions = card.state.suggestions;
        suite.assert(Array.isArray(suggestions), 'Suggestions should be an array');
        suite.assert(suggestions.length > 0, 'Should have at least one suggestion');
    });

    return suite;
}

// Auto-run tests in browser environment
if (typeof window !== 'undefined') {
    window.runComponentTests = async () => {
        const suite = createComponentTests();
        return await suite.run();
    };

    // Run tests automatically if URL has ?test=true
    if (window.location.search.includes('test=true')) {
        setTimeout(async () => {
            const results = await window.runComponentTests();
            window.testResults = results;
        }, 1000);
    }
}

export { createComponentTests, ComponentTestSuite };
