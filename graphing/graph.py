import json
import networkx as nx
import plotly.graph_objects as go
import numpy as np

# Load JSON data
with open('graph_data/tuples_table_v1.json', 'r') as file:
    data = json.load(file)

# Create a directed graph
G = nx.DiGraph()

# Add nodes and edges
for item in data:
    source = item['source_screen_id']
    destination = item['destination_screen_id']
    action = item['action_contentDesc']

    G.add_node(source)
    G.add_node(destination)
    G.add_edge(source, destination, label=action)

# Calculate node activity (in-degree + out-degree)
node_activity = {node: G.in_degree(node) + G.out_degree(node) for node in G.nodes()}

# Use spring layout to position nodes
pos = nx.spring_layout(G, k=0.9, iterations=50)

# Create edge traces with arrows
edge_traces = []
for edge in G.edges():
    x0, y0 = pos[edge[0]]
    x1, y1 = pos[edge[1]]

    # Calculate the angle of the edge
    angle = np.arctan2(y1 - y0, x1 - x0)

    # Create the edge line
    edge_trace = go.Scatter(
        x=[x0, x1],
        y=[y0, y1],
        line=dict(width=1, color='#888'),
        hoverinfo='none',
        mode='lines'
    )

    # Create the arrowhead as a small triangle near the destination node
    arrow_size = 0.015
    arrow_width = 0.01

    arrow_point1 = [x1, y1]
    arrow_point2 = [x1 - arrow_size * np.cos(angle) + arrow_width * np.sin(angle),
                    y1 - arrow_size * np.sin(angle) - arrow_width * np.cos(angle)]
    arrow_point3 = [x1 - arrow_size * np.cos(angle) - arrow_width * np.sin(angle),
                    y1 - arrow_size * np.sin(angle) + arrow_width * np.cos(angle)]

    arrow_trace = go.Scatter(
        x=[arrow_point1[0], arrow_point2[0], arrow_point3[0], arrow_point1[0]],
        y=[arrow_point1[1], arrow_point2[1], arrow_point3[1], arrow_point1[1]],
        fill='toself',
        fillcolor='red',
        line=dict(width=0),
        hoverinfo='none',
        mode='lines'
    )

    edge_traces.append(edge_trace)
    edge_traces.append(arrow_trace)

# Create node trace
node_x = []
node_y = []
node_colors = []
node_sizes = []
node_texts = []
for node in G.nodes():
    x, y = pos[node]
    node_x.append(x)
    node_y.append(y)
    node_colors.append(node_activity[node])
    node_sizes.append(10 + node_activity[node] * 2)  # Adjust size based on activity
    node_texts.append(f"Screen: {node}<br>Activity: {node_activity[node]}")

node_trace = go.Scatter(
    x=node_x, y=node_y,
    mode='markers+text',
    hoverinfo='text',
    marker=dict(
        showscale=True,
        colorscale='YlOrRd',
        size=node_sizes,
        color=node_colors,
        colorbar=dict(
            thickness=15,
            title='Node Activity',
            xanchor='left',
            titleside='right'
        )
    ),
    text=[str(node) for node in G.nodes()],
    textposition="top center",
    hovertext=node_texts
)

# Create the figure
fig = go.Figure(data=edge_traces + [node_trace],
                layout=go.Layout(
                    title='Graph Representation with Directed Edges and Activity Heatmap',
                    titlefont_size=16,
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20, l=5, r=5, t=40),
                    annotations=[dict(
                        text="Python code: <a href='https://plotly.com/ipython-notebooks/network-graphs/'> https://plotly.com/ipython-notebooks/network-graphs/</a>",
                        showarrow=False,
                        xref="paper", yref="paper",
                        x=0.005, y=-0.002)],
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                )

# Show the plot
fig.show()
