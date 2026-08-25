const CARD_TAG = "stp-token-renewal-card";

const DEFAULT_ENTITIES = {
  status: ["sensor", "token_status"],
  valid: ["binary_sensor", "token_valid"],
  remaining: ["sensor", "token_remaining_hours"],
  expires: ["sensor", "token_expires_at"],
  lastCheck: ["sensor", "token_last_check"],
  candidate: ["binary_sensor", "new_trial_token_available"],
  problem: ["binary_sensor", "updater_problem"],
};

const escapeHtml = (value) =>
  String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

class StpTokenRenewalCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass = undefined;
  }

  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = config || {};
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 2;
  }

  _resolveEntity(key) {
    const explicit = this._config?.entities?.[key];
    if (explicit) {
      return explicit;
    }

    const definition = DEFAULT_ENTITIES[key];
    if (!definition) {
      return undefined;
    }

    const [domain, suffix] = definition;
    const base = `${domain}.stp_token_updater_${suffix}`;
    if (!this._hass) {
      return base;
    }
    if (this._hass.states?.[base]) {
      return base;
    }

    return (
      Object.keys(this._hass.states || {}).find((entityId) =>
        entityId.startsWith(`${base}_`),
      ) || base
    );
  }

  _state(entityId) {
    return entityId ? this._hass?.states?.[entityId] : undefined;
  }

  _display(entityId) {
    const stateObj = this._state(entityId);
    if (!stateObj) {
      return "—";
    }

    if (typeof this._hass?.formatEntityState === "function") {
      try {
        return this._hass.formatEntityState(stateObj);
      } catch (_error) {
        // Fall back to the raw state if frontend formatting is unavailable.
      }
    }
    return stateObj.state;
  }

  _moreInfo(entityId) {
    if (!this._state(entityId)) {
      return;
    }
    this.dispatchEvent(
      new CustomEvent("hass-more-info", {
        bubbles: true,
        composed: true,
        detail: { entityId },
      }),
    );
  }

  _chip(icon, label, value, entityId, extraClass = "") {
    const available = Boolean(this._state(entityId));
    return `
      <button
        class="chip ${extraClass}"
        data-entity="${escapeHtml(entityId)}"
        ${available ? "" : "disabled"}
        title="${escapeHtml(label)}"
      >
        <ha-icon icon="${escapeHtml(icon)}"></ha-icon>
        <span class="chip-text">
          <span class="chip-label">${escapeHtml(label)}</span>
          <span class="chip-value">${escapeHtml(value)}</span>
        </span>
      </button>
    `;
  }

  _render() {
    if (!this.shadowRoot) {
      return;
    }

    const statusEntity = this._resolveEntity("status");
    const validEntity = this._resolveEntity("valid");
    const remainingEntity = this._resolveEntity("remaining");
    const expiresEntity = this._resolveEntity("expires");
    const lastCheckEntity = this._resolveEntity("lastCheck");
    const candidateEntity = this._resolveEntity("candidate");
    const problemEntity = this._resolveEntity("problem");

    const validState = this._state(validEntity)?.state;
    const candidateState = this._state(candidateEntity)?.state;
    const problemState = this._state(problemEntity)?.state;
    const title = this._config?.title || "Token Renewal";
    const status = this._display(statusEntity);
    const hasStpEntities = Boolean(this._state(statusEntity));

    let healthClass = "unknown";
    let healthIcon = "mdi:shield-question-outline";
    let healthText = "Unknown";

    if (problemState === "on") {
      healthClass = "problem";
      healthIcon = "mdi:alert-circle-outline";
      healthText = "Problem";
    } else if (validState === "on") {
      healthClass = "valid";
      healthIcon = "mdi:shield-check-outline";
      healthText = "Valid";
    } else if (validState === "off") {
      healthClass = "invalid";
      healthIcon = "mdi:shield-alert-outline";
      healthText = "Invalid";
    }

    const candidateClass = candidateState === "on" ? "candidate-active" : "";
    const candidateText = candidateState === "on" ? "Available" : "None";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
        }

        ha-card {
          overflow: hidden;
        }

        .card {
          padding: 16px;
        }

        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 12px;
          margin-bottom: 14px;
        }

        .title-wrap {
          display: flex;
          align-items: center;
          min-width: 0;
          gap: 12px;
        }

        .title-icon {
          --mdc-icon-size: 28px;
          color: var(--primary-color);
          flex: 0 0 auto;
        }

        .title-block {
          min-width: 0;
        }

        .title {
          color: var(--primary-text-color);
          font-size: 16px;
          font-weight: 500;
          line-height: 1.25;
        }

        .status {
          color: var(--secondary-text-color);
          font-size: 13px;
          line-height: 1.35;
          margin-top: 2px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .health {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          border-radius: 999px;
          padding: 5px 9px;
          background: var(--secondary-background-color);
          color: var(--secondary-text-color);
          font-size: 12px;
          white-space: nowrap;
        }

        .health ha-icon {
          --mdc-icon-size: 17px;
        }

        .health.valid {
          color: var(--success-color, var(--primary-color));
        }

        .health.invalid,
        .health.problem {
          color: var(--error-color);
        }

        .chips {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 8px;
        }

        .chip {
          appearance: none;
          border: 0;
          border-radius: 12px;
          background: var(--secondary-background-color);
          color: var(--primary-text-color);
          cursor: pointer;
          display: flex;
          align-items: center;
          gap: 8px;
          min-width: 0;
          padding: 9px 10px;
          text-align: left;
          font: inherit;
        }

        .chip:not(:disabled):hover {
          background: var(--card-background-color);
          box-shadow: inset 0 0 0 1px var(--divider-color);
        }

        .chip:disabled {
          cursor: default;
          opacity: 0.55;
        }

        .chip ha-icon {
          --mdc-icon-size: 20px;
          color: var(--secondary-text-color);
          flex: 0 0 auto;
        }

        .chip.candidate-active ha-icon,
        .chip.candidate-active .chip-value {
          color: var(--success-color, var(--primary-color));
        }

        .chip-text {
          display: flex;
          flex-direction: column;
          min-width: 0;
        }

        .chip-label {
          color: var(--secondary-text-color);
          font-size: 10px;
          line-height: 1.2;
        }

        .chip-value {
          font-size: 12px;
          line-height: 1.35;
          margin-top: 1px;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .missing {
          color: var(--secondary-text-color);
          font-size: 13px;
          padding: 2px 0 4px;
        }

        @media (max-width: 700px) {
          .chips {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }
      </style>

      <ha-card>
        <div class="card">
          <div class="header">
            <div class="title-wrap">
              <ha-icon class="title-icon" icon="mdi:lock-open-check-outline"></ha-icon>
              <div class="title-block">
                <div class="title">${escapeHtml(title)}</div>
                <div class="status">${escapeHtml(status)}</div>
              </div>
            </div>
            <div class="health ${healthClass}">
              <ha-icon icon="${healthIcon}"></ha-icon>
              <span>${escapeHtml(healthText)}</span>
            </div>
          </div>

          ${
            hasStpEntities
              ? `<div class="chips">
                  ${this._chip("mdi:timer-sand", "Remaining", this._display(remainingEntity), remainingEntity)}
                  ${this._chip("mdi:calendar-clock", "Expires", this._display(expiresEntity), expiresEntity)}
                  ${this._chip("mdi:clock-check-outline", "Last check", this._display(lastCheckEntity), lastCheckEntity)}
                  ${this._chip("mdi:key-plus", "New token", candidateText, candidateEntity, candidateClass)}
                </div>`
              : `<div class="missing">STP Token Updater entities were not found. Configure the integration first or override the entity IDs in YAML.</div>`
          }
        </div>
      </ha-card>
    `;

    this.shadowRoot.querySelectorAll("[data-entity]").forEach((element) => {
      element.addEventListener("click", () => this._moreInfo(element.dataset.entity));
    });
  }
}

if (!customElements.get(CARD_TAG)) {
  customElements.define(CARD_TAG, StpTokenRenewalCard);
}

window.customCards = window.customCards || [];
if (!window.customCards.some((card) => card.type === CARD_TAG)) {
  window.customCards.push({
    type: CARD_TAG,
    name: "Token Renewal",
    preview: true,
    description: "Compact status card for STP token renewal.",
    documentationURL:
      "https://github.com/CaneTLOTW/stp-token-updater#dashboard-card",
    getEntitySuggestion: (_hass, entityId) => {
      if (!String(entityId).includes("stp_token_updater_")) {
        return null;
      }
      return {
        config: { type: `custom:${CARD_TAG}` },
      };
    },
  });
}
