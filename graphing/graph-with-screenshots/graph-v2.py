import json
import os
import sqlite3

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

# todo connect this script to run automatically after the traverse script with less setup steps

""""Steps to use this script to create a graph of an app
1- update the current_package variable with app package
2- create an empty folder called same as the name of your package
3- inside this folder provide the screenshots folder and the .db file you got from the traverse script

The script will generate a PDF file containing the Graph inside the same folder you created
"""
current_package = "com.myfitnesspal.android"


def add_image(ax, im, x, y, zoom=1):
    im = OffsetImage(im, zoom=zoom)
    ab = AnnotationBbox(im, (x, y), xycoords="data", frameon=False)
    ax.add_artist(ab)


""""sql code to extract the tuples_table_v1 from the db file and turn it to JSON format"""
# Path to the SQLite database file
db_file = f"{current_package}/{current_package}.db"

# Connect to the SQLite database
conn = sqlite3.connect(db_file)

# Query the tuples_table_v1 table
query = "SELECT * FROM tuples_table_v1"
df = pd.read_sql_query(query, conn)

# Convert the dataframe to JSON format
json_data = df.to_json(orient="records")

# Save the JSON output to a file
json_file = f"{current_package}/{current_package}_tuples_table_v1.json"
with open(json_file, "w") as file:
    file.write(json_data)

# Close the database connection
conn.close()

""""use the extracted JSON file to build the graph """

# Load JSON data from file
with open(f"{current_package}/{current_package}_tuples_table_v1.json", "r") as file:
    data_list = json.load(file)

# Create a directed graph
G = nx.DiGraph()

# Add nodes and edges
for data in data_list:
    source = data["source_screen_id"]
    dest = data["destination_screen_id"]
    G.add_node(source)
    G.add_node(dest)
    edge_label = (
        data["action_text"] or data["action_hint"] or data["action_contentDesc"]
    )
    G.add_edge(source, dest, label=edge_label)

# Set up the plot
fig, ax = plt.subplots(figsize=(30, 24))

# Use kamada_kawai_layout for better node separation
pos = nx.kamada_kawai_layout(G)

# Scale and center the layout
pos_array = nx.spring_layout(G, pos=pos, k=1.5, iterations=100)

# Draw the graph
nx.draw(G, pos_array, ax=ax, with_labels=False, node_size=0, arrows=False)

# Add node labels and images
screenshot_dir = f"{current_package}_screenshots"
for node, (x, y) in pos_array.items():
    img_path = os.path.join(screenshot_dir, f"screen{node}.png")
    if os.path.exists(img_path):
        img = plt.imread(img_path)
        add_image(ax, img, x, y, zoom=0.05)  # Reduced zoom by 50%
    else:
        print(f"Warning: Image not found for node {node}")

# Add edge labels and arrows
edge_labels = nx.get_edge_attributes(G, "label")
for (node1, node2), label in edge_labels.items():
    x1, y1 = pos_array[node1]
    x2, y2 = pos_array[node2]

    # Truncate label if necessary
    if len(label) > 10:
        label = label[:10] + "..."

    # Calculate the position for the label
    label_pos = ((x1 + x2) / 2, (y1 + y2) / 2)

    # Add the edge label
    ax.text(
        label_pos[0],
        label_pos[1],
        label,
        fontsize=8,
        ha="center",
        va="center",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.7),
    )

    # Add an arrow
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="->", color="red", lw=1),
        annotation_clip=False,
    )

# Remove axis
ax.axis("off")

# Enable scrolling for the plot
fig.canvas.mpl_connect("scroll_event", lambda event: on_scroll(event, ax))


def on_scroll(event, ax):
    if event.button == "up":
        ax.set_xlim(ax.get_xlim()[0], ax.get_xlim()[1] * 0.9)
        ax.set_ylim(ax.get_ylim()[0], ax.get_ylim()[1] * 0.9)
    elif event.button == "down":
        ax.set_xlim(ax.get_xlim()[0], ax.get_xlim()[1] * 1.1)
        ax.set_ylim(ax.get_ylim()[0], ax.get_ylim()[1] * 1.1)
    fig.canvas.draw_idle()


# Show the plot
plt.tight_layout()
plt.savefig(f"{current_package}/{current_package}_graph.pdf", dpi=300, bbox_inches="tight")
# plt.show()
