"""
Result visualization and export capabilities.

Provides endpoints and utilities for:
- Result visualization (plots, charts, graphs)
- Export to multiple formats (JSON, CSV, Parquet, PDF)
- Interactive dashboards
- Comparison plots
- Convergence visualization
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import plotly.graph_objects as go
from numpy.typing import NDArray


class VisualizationType(Enum):
    """Types of visualizations available."""

    LINE_PLOT = "line_plot"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    CONVERGENCE_PLOT = "convergence_plot"
    PARETO_FRONT = "pareto_front"
    CIRCUIT_DIAGRAM = "circuit_diagram"
    HISTOGRAM = "histogram"
    BAR_CHART = "bar_chart"


class ExportFormat(Enum):
    """Export formats."""

    JSON = "json"
    CSV = "csv"
    PARQUET = "parquet"
    PDF = "pdf"
    PNG = "png"
    SVG = "svg"


@dataclass
class VisualizationData:
    """Container for visualization data."""

    type: VisualizationType
    plot_data: Any
    layout: dict[str, Any]
    title: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ConvergencePlot:
    """Create convergence plots for optimization results."""

    @staticmethod
    def create(
        objective_history: list[float],
        title: str = "Convergence History",
    ) -> VisualizationData:
        """Create a convergence line plot."""
        iterations = list(range(len(objective_history)))

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=iterations,
                y=objective_history,
                mode="lines+markers",
                name="Objective Value",
                line={"color": "blue", "width": 2},
                marker={"size": 6},
            )
        )

        fig.update_layout(
            title=title,
            xaxis_title="Iteration",
            yaxis_title="Objective Value",
            hovermode="x unified",
        )

        return VisualizationData(
            type=VisualizationType.CONVERGENCE_PLOT,
            plot_data=fig,
            layout=fig.layout,
            title=title,
            description=f"Convergence over {len(objective_history)} iterations",
        )


class ParetoFrontPlot:
    """Create Pareto front visualizations for multi-objective optimization."""

    @staticmethod
    def create(
        objective_values: NDArray[np.float64],
        point_labels: list[str] | None = None,
        title: str = "Pareto Front",
    ) -> VisualizationData:
        """Create a Pareto front scatter plot."""
        fig = go.Figure()

        if point_labels:
            text = point_labels
        else:
            text = None

        fig.add_trace(
            go.Scatter(
                x=objective_values[:, 0],
                y=objective_values[:, 1],
                mode="markers",
                text=text,
                marker={
                    "size": 10,
                    "color": objective_values[:, 0],
                    "colorscale": "Viridis",
                    "showscale": True,
                    "colorbar": {"title": "Objective 1"},
                },
                name="Solutions",
            )
        )

        fig.update_layout(
            title=title,
            xaxis_title="Objective 1 (Minimize)",
            yaxis_title="Objective 2 (Minimize)",
            hovermode="closest",
        )

        return VisualizationData(
            type=VisualizationType.PARETO_FRONT,
            plot_data=fig,
            layout=fig.layout,
            title=title,
            description=f"Pareto front with {len(objective_values)} solutions",
            metadata={"num_solutions": len(objective_values)},
        )


class MeasurementHistogram:
    """Create measurement count histograms."""

    @staticmethod
    def create(
        counts: dict[str, int],
        num_qubits: int,
        title: str = "Measurement Outcomes",
    ) -> VisualizationData:
        """Create a histogram of measurement results."""
        bitstrings = list(counts.keys())
        values = list(counts.values())

        fig = go.Figure(data=[go.Bar(x=bitstrings, y=values, name="Counts")])

        fig.update_layout(
            title=title,
            xaxis_title="Measurement Outcome",
            yaxis_title="Count",
            xaxis_tickangle=-45,
        )

        return VisualizationData(
            type=VisualizationType.HISTOGRAM,
            plot_data=fig,
            layout=fig.layout,
            title=title,
            description=f"Outcomes for {num_qubits}-qubit circuit",
        )


class QuantumCircuitVisualizer:
    """Visualize quantum circuits."""

    @staticmethod
    def create_png(
        circuit: Any,
        filename: str | None = None,
        scale: float = 1.0,
        output: io.BytesIO | None = None,
    ) -> bytes:
        """Create PNG image of circuit."""
        try:
            from qiskit.visualization import circuit_drawer

            buf = output or io.BytesIO()

            # Draw circuit to PNG
            circuit_drawer(
                circuit,
                output="mpl",
                scale=scale,
                filename=filename,
            )

            if output:
                return buf.getvalue()

            return buf.getvalue()
        except ImportError as e:
            raise ImportError("matplotlib is required for circuit visualization") from e
        except Exception as e:
            raise RuntimeError(f"Failed to generate circuit visualization: {e}") from e

    @staticmethod
    def create_qasm(
        circuit: Any,
    ) -> str:
        """Get QASM representation of circuit."""
        return circuit.qasm()

    @staticmethod
    def create_qpy(
        circuit: Any,
    ) -> bytes:
        """Get QPY serialized circuit."""
        try:
            from qiskit.qpy import dump

            buf = io.BytesIO()
            dump(circuit, buf)
            return buf.getvalue()
        except ImportError as e:
            raise ImportError("qiskit-qpy is required for QPY serialization") from e


class PlotlyExporter:
    """Export visualizations to various formats."""

    @staticmethod
    def to_html(visualization: VisualizationData) -> str:
        """Export visualization to HTML."""
        return visualization.plot_data.to_html(include_plotlyjs=True)

    @staticmethod
    def to_json(visualization: VisualizationData) -> str:
        """Export visualization to JSON."""
        return visualization.plot_data.to_json()

    @staticmethod
    def to_png(visualization: VisualizationData) -> bytes:
        """Export visualization to PNG."""
        try:
            return visualization.plot_data.to_image(format="png", engine="kaleido")
        except ImportError as e:
            raise ImportError(
                "kaleido is required for image export. Install with: pip install kaleido"
            ) from e

    @staticmethod
    def to_svg(visualization: VisualizationData) -> str:
        """Export visualization to SVG."""
        return visualization.plot_data.to_image(format="svg", engine="kaleido").decode()


class ResultExporter:
    """Export optimization results to various formats."""

    @staticmethod
    def to_json(data: dict[str, Any]) -> str:
        """Export result to JSON."""
        return json.dumps(data, indent=2, default=str)

    @staticmethod
    def to_csv(
        data: dict[str, Any],
        filename: str = "results.csv",
    ) -> str:
        """Export result to CSV format."""
        try:
            import pandas as pd

            # Flatten nested structures for CSV
            flat_data = ResultExporter._flatten_for_csv(data)
            df = pd.DataFrame([flat_data])

            csv_data = df.to_csv(index=False)
            return csv_data
        except ImportError as e:
            raise ImportError("pandas is required for CSV export") from e

    @staticmethod
    def to_parquet(
        data: dict[str, Any],
        filename: str = "results.parquet",
    ) -> bytes:
        """Export result to Parquet format."""
        try:
            import pandas as pd
            import pyarrow as pa

            flat_data = ResultExporter._flatten_for_csv(data)
            df = pd.DataFrame([flat_data])

            # Use in-memory buffer
            output = io.BytesIO()
            df.to_parquet(output, engine="pyarrow")

            return output.getvalue()
        except ImportError as e:
            raise ImportError("pandas and pyarrow are required for Parquet export") from e

    @staticmethod
    def _flatten_for_csv(data: dict[str, Any]) -> dict[str, Any]:
        """Flatten nested data for CSV export."""
        result = {}

        for key, value in data.items():
            if isinstance(value, (list, tuple)):
                if len(value) == 0:
                    result[key] = "[]"
                elif len(value) == 1:
                    result[key] = str(value[0])
                else:
                    result[key] = str(value)
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    result[f"{key}_{sub_key}"] = str(sub_value)
            elif value is None:
                result[key] = ""
            else:
                result[key] = str(value)

        return result

    @staticmethod
    def to_pdf_report(
        data: dict[str, Any],
        visualizations: list[VisualizationData],
        title: str = "Optimization Report",
    ) -> bytes:
        """Generate PDF report with visualizations."""
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.styles import getSampleStyleSheet
            from reportlab.lib.units import inch
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

            # Create PDF
            output = io.BytesIO()
            doc = SimpleDocTemplate(output, pagesize=letter)
            styles = getSampleStyleSheet()
            story = []

            # Add title
            story.append(Paragraph(title, styles["Title"]))
            story.append(Spacer(1, 0.2 * inch))

            # Add timestamp
            story.append(
                Paragraph(
                    f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                    styles["Normal"],
                )
            )
            story.append(Spacer(1, 0.3 * inch))

            # Add key results
            story.append(Paragraph("Key Results:", styles["Heading2"]))
            for key, value in data.items():
                if key not in ["metadata", "raw_data"]:
                    story.append(Paragraph(f"{key}: {value}", styles["Normal"]))

            story.append(Spacer(1, 0.3 * inch))

            # Add visualizations if available
            if visualizations:
                story.append(Paragraph("Visualizations:", styles["Heading2"]))

                exporter = PlotlyExporter()
                for viz in visualizations:
                    try:
                        exporter.to_png(viz)
                        # In production, would add the image to the PDF
                        story.append(Paragraph(viz.title, styles["Heading3"]))
                    except Exception as e:
                        story.append(
                            Paragraph(f"Could not export {viz.title}: {e}", styles["Normal"])
                        )

            doc.build(story)
            return output.getvalue()

        except ImportError as e:
            raise ImportError("reportlab is required for PDF export") from e


class ComparisonPlots:
    """Create comparison plots for multiple results."""

    @staticmethod
    def create_convergence_comparison(
        results: list[dict[str, Any]],
        labels: list[str],
    ) -> VisualizationData:
        """Create comparison plot for multiple convergence histories."""
        fig = go.Figure()

        for _i, (result, label) in enumerate(zip(results, labels, strict=False)):
            if "objective_history" in result:
                history = result["objective_history"]
                iterations = list(range(len(history)))

                fig.add_trace(
                    go.Scatter(
                        x=iterations,
                        y=history,
                        mode="lines",
                        name=label,
                        line={"width": 2},
                    )
                )

        fig.update_layout(
            title="Convergence Comparison",
            xaxis_title="Iteration",
            yaxis_title="Objective Value",
            hovermode="x unified",
        )

        return VisualizationData(
            type=VisualizationType.LINE_PLOT,
            plot_data=fig,
            layout=fig.layout,
            title="Convergence Comparison",
            description="Comparing convergence of multiple optimization runs",
        )

    @staticmethod
    def create_backend_comparison(
        backend_stats: dict[str, dict[str, Any]],
    ) -> VisualizationData:
        """Create bar chart comparing backend performance."""
        backends = list(backend_stats.keys())
        metrics = list(backend_stats[backends[0]].keys())

        fig = go.Figure()

        for metric in metrics:
            values = [backend_stats[b][metric] for b in backends]
            fig.add_trace(
                go.Bar(
                    name=metric,
                    x=backends,
                    y=values,
                )
            )

        fig.update_layout(
            title="Backend Performance Comparison",
            barmode="group",
            xaxis_title="Backend",
            yaxis_title="Value",
        )

        return VisualizationData(
            type=VisualizationType.BAR_CHART,
            plot_data=fig,
            layout=fig.layout,
            title="Backend Performance",
            description="Comparing performance across quantum backends",
        )


class ResultVisualizer:
    """
    Main interface for result visualization and export.

    Provides high-level API for common visualization tasks.
    """

    @staticmethod
    def create_dashboard(
        job_result: dict[str, Any],
    ) -> dict[str, VisualizationData]:
        """Create a complete dashboard with multiple visualizations."""
        visualizations = {}

        # Convergence plot
        if "objective_history" in job_result:
            visualizations["convergence"] = ConvergencePlot.create(
                job_result["objective_history"], "Optimization Convergence"
            )

        # Measurement histogram
        if "counts" in job_result:
            visualizations["measurements"] = MeasurementHistogram.create(
                job_result["counts"], job_result.get("num_qubits", 10), "Measurement Outcomes"
            )

        return visualizations

    @staticmethod
    def export_multiple_formats(
        data: dict[str, Any],
        formats: list[ExportFormat],
    ) -> dict[ExportFormat, Any]:
        """Export result in multiple formats."""
        exporter = ResultExporter()
        exports = {}

        if ExportFormat.JSON in formats:
            exports[ExportFormat.JSON] = exporter.to_json(data)

        if ExportFormat.CSV in formats:
            exports[ExportFormat.CSV] = exporter.to_csv(data)

        if ExportFormat.PARQUET in formats:
            exports[ExportFormat.PARQUET] = exporter.to_parquet(data)

        if ExportFormat.PDF in formats and len(exports) > 0:
            # Create visualizations for PDF
            dashboards = ResultVisualizer.create_dashboard(data)
            visualizations = list(dashboards.values())

            exports[ExportFormat.PDF] = exporter.to_pdf_report(data, visualizations)

        return exports


__all__ = [
    "VisualizationType",
    "ExportFormat",
    "VisualizationData",
    "ConvergencePlot",
    "ParetoFrontPlot",
    "MeasurementHistogram",
    "QuantumCircuitVisualizer",
    "PlotlyExporter",
    "ResultExporter",
    "ComparisonPlots",
    "ResultVisualizer",
]
