from backend.app.graph.nodes import Node
from app.graph.edge import Edge


class ConversationGraph:

    def __init__(self):

        self.nodes = {}

        self.edges = []

    def add_node(self, node: Node):

        self.nodes[node.id] = node

    def add_edge(self, edge: Edge):

        self.edges.append(edge)

    def next_nodes(self, current):

        result = []

        for edge in self.edges:

            if edge.source == current:

                result.append(self.nodes[edge.target])

        return result