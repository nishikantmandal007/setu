import plotly.graph_objects as go
from plotly.subplots import make_subplots


def plot_bending_moment(forces):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=forces.stations_m, y=forces.moment_kn_m,
        mode="lines", name="Moment",
        fill="tozeroy",
    ))
    fig.update_layout(
        xaxis_title="Station (m)",
        yaxis_title="Bending moment (kN·m)",
        yaxis_autorange="reversed",
    )
    return fig


def plot_shear_force(forces):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=forces.stations_m, y=forces.shear_kn,
        mode="lines", name="Shear",
        fill="tozeroy",
    ))
    fig.update_layout(
        xaxis_title="Station (m)",
        yaxis_title="Shear force (kN)",
    )
    return fig


def plot_torsion(forces):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=forces.stations_m, y=forces.torsion_kn_m,
        mode="lines", name="Torsion",
        fill="tozeroy",
    ))
    fig.update_layout(
        xaxis_title="Station (m)",
        yaxis_title="Torsion (kN·m)",
    )
    return fig


def plot_deflection(deflections):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=deflections.stations_m, y=deflections.vertical_m * 1000,
        mode="lines", name="Deflection",
        fill="tozeroy",
    ))
    fig.update_layout(
        xaxis_title="Station (m)",
        yaxis_title="Vertical deflection (mm)",
    )
    return fig


def plot_girder_summary(forces, deflections):
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        subplot_titles=(
            "Bending Moment", "Shear Force",
            "Torsion", "Deflection",
        ),
        vertical_spacing=0.06,
    )
    fig.add_trace(go.Scatter(
        x=forces.stations_m, y=forces.moment_kn_m,
        mode="lines", name="Moment (kN·m)", fill="tozeroy",
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=forces.stations_m, y=forces.shear_kn,
        mode="lines", name="Shear (kN)", fill="tozeroy",
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=forces.stations_m, y=forces.torsion_kn_m,
        mode="lines", name="Torsion (kN·m)", fill="tozeroy",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=deflections.stations_m, y=deflections.vertical_m * 1000,
        mode="lines", name="Deflection (mm)", fill="tozeroy",
    ), row=4, col=1)
    fig.update_yaxes(title_text="kN·m", autorange="reversed", row=1, col=1)
    fig.update_yaxes(title_text="kN", row=2, col=1)
    fig.update_yaxes(title_text="kN·m", row=3, col=1)
    fig.update_yaxes(title_text="mm", row=4, col=1)
    fig.update_xaxes(title_text="Station (m)", row=4, col=1)
    fig.update_layout(height=900, showlegend=False)
    return fig


def plot_envelope(envelope):
    cases = list(set(envelope.governing_case))
    colors = _case_colors(cases)
    fig = go.Figure()
    for case in cases:
        mask = [c == case for c in envelope.governing_case]
        x = envelope.stations_m[mask]
        y = envelope.moment_kn_m[mask]
        fig.add_trace(go.Scatter(
            x=x, y=y,
            mode="markers+lines", name=case,
            marker=dict(color=colors[case]),
            line=dict(color=colors[case]),
        ))
    fig.update_layout(
        xaxis_title="Station (m)",
        yaxis_title="Governing moment (kN·m)",
        yaxis_autorange="reversed",
    )
    return fig


def _case_colors(cases):
    palette = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        "#bcbd22", "#17becf",
    ]
    return {case: palette[i % len(palette)] for i, case in enumerate(cases)}
