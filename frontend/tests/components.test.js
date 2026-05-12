import { beforeEach, describe, expect, it, vi } from "vitest";

import Component from "../js/components/Component.js";
import { Modal } from "../js/components/Modal.js";
import { ModalManager } from "../js/components/ModalManager.js";

const flushUpdates = () => new Promise((resolve) => queueMicrotask(resolve));

class CounterComponent extends Component {
  constructor() {
    super();
    this.state = { count: 0 };
    this.renderCount = 0;
  }

  render() {
    this.renderCount += 1;
    this.element.innerHTML = `<button type="button">${this.state.count}</button>`;
  }
}

describe("component system", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    document.body.style.overflow = "";
    vi.stubGlobal("requestAnimationFrame", (callback) => setTimeout(callback, 0));
  });

  it("mounts and batches state updates", async () => {
    const component = new CounterComponent();
    const root = document.createElement("main");
    document.body.appendChild(root);

    component.mount(root);
    expect(root.querySelector("button")?.textContent).toBe("0");

    component.setState({ count: 1 });
    await flushUpdates();

    expect(root.querySelector("button")?.textContent).toBe("1");
    expect(component.renderCount).toBe(2);
  });

  it("cleans up registered event listeners on unmount", () => {
    const component = new CounterComponent();
    const button = document.createElement("button");
    let clicks = 0;

    component.addEvent(button, "click", () => {
      clicks += 1;
    }, { allowDefault: true });

    button.click();
    component.unmount();
    button.click();

    expect(clicks).toBe(1);
  });

  it("renders modal titles safely and toggles body scroll", async () => {
    const root = document.createElement("section");
    document.body.appendChild(root);
    const modal = new Modal({ title: "<script>alert(1)</script>" });

    modal.mount(root);
    modal.open();
    await flushUpdates();

    expect(root.querySelector(".modal-title")?.innerHTML).toBe(
      "&lt;script&gt;alert(1)&lt;/script&gt;",
    );
    expect(document.body.style.overflow).toBe("hidden");

    modal.close();
    await flushUpdates();

    expect(root.querySelector(".modal")).toBeNull();
    expect(document.body.style.overflow).toBe("");
  });

  it("creates, opens, closes, and unregisters modals through ModalManager", () => {
    const manager = new ModalManager();
    manager.init(document.body);

    const modal = manager.create("settings", { title: "Settings" });

    expect(manager.getModal("settings")).toBe(modal);
    expect(manager.open("settings")).toBe(true);
    expect(manager.isOpen("settings")).toBe(true);
    expect(manager.close("settings")).toBe(true);
    expect(manager.isOpen("settings")).toBe(false);
    expect(manager.unregister("settings")).toBe(true);
    expect(manager.getModal("settings")).toBeUndefined();
  });
});
