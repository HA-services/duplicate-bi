/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useState } from "@odoo/owl";

export class AxsyncDuplicateDashboard extends Component {
    static template = "axsync_duplicate_invoice_guard.Dashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ days: 90, data: null });
        this.periods = [
            { value: 30, label: "Last 30 days" },
            { value: 90, label: "Last 90 days" },
            { value: 180, label: "Last 6 months" },
            { value: 365, label: "Last 12 months" },
            { value: 0, label: "All time" },
        ];
        onWillStart(() => this.load());
    }

    async load() {
        this.state.data = await this.orm.call(
            "axsync.duplicate.case", "get_dashboard_data", [this.state.days]
        );
    }

    async onPeriodChange(ev) {
        this.state.days = parseInt(ev.target.value, 10);
        await this.load();
    }

    formatValue(tile) {
        const num = Number(tile.value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
        return `${tile.prefix || ""}${num}${tile.suffix || ""}`;
    }

    formatAmount(value) {
        return `${this.state.data.symbol} ${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
    }

    openTile(tile) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: tile.label,
            res_model: tile.model,
            views: [[false, "list"], [false, "pivot"], [false, "graph"]],
            domain: tile.domain,
        });
    }

    openCase(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "axsync.duplicate.case",
            res_id: id,
            views: [[false, "form"]],
        });
    }

    openPartner(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: "Cases",
            res_model: "axsync.duplicate.case",
            views: [[false, "list"], [false, "pivot"], [false, "graph"]],
            domain: [["partner_id", "=", id]],
        });
    }

    openQueue() {
        this.action.doAction("axsync_duplicate_invoice_guard.axsync_duplicate_case_review_action");
    }
}

registry.category("actions").add("axsync_duplicate_dashboard", AxsyncDuplicateDashboard);
