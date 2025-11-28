
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Optional
import graphviz

def load_convo(file_path: str) -> Dict:
    """Load convo JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)

def get_node_color(node_type: str) -> str:
    """Get color based on node type."""
    colors = {
        'start': '#4CAF50',      # Green
        'end': '#F44336',        # Red
        'menu': '#2196F3',       # Blue
        'message': '#FF9800',    # Orange
        'collect_input': '#9C27B0',  # Purple
        'question': '#00BCD4',   # Cyan
        'action': '#FFC107',     # Amber
        'condition': '#795548',  # Brown
        'api_call': '#607D8B',   # Blue Grey
        'jump': '#E91E63',       # Pink
        'validation': '#3F51B5', # Indigo
        'collect_data': '#9C27B0',  # Purple (same as collect_input)
        'process': '#FFC107',    # Amber (same as action)
    }
    return colors.get(node_type, '#9E9E9E')  # Grey as default

def get_node_shape(node_type: str) -> str:
    """Get shape based on node type."""
    shapes = {
        'start': 'doublecircle',
        'end': 'doublecircle',
        'menu': 'box',
        'message': 'ellipse',
        'collect_input': 'diamond',
        'collect_data': 'diamond',
        'question': 'parallelogram',
        'action': 'hexagon',
        'process': 'hexagon',
        'condition': 'diamond',
        'api_call': 'cylinder',
        'jump': 'invtriangle',
        'validation': 'octagon'
    }
    return shapes.get(node_type, 'ellipse')

def truncate_text(text: str, max_length: int = 40) -> str:
    """Truncate text to max length."""
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + '...'

def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))

def create_node_label(node: Dict) -> str:
    """Create a formatted label for the node."""
    node_id = node.get('id', 'unknown')
    node_type = node.get('type', 'unknown')
    name = node.get('name', node_id)
    
    # Truncate name if too long
    name = truncate_text(name, 30)
    name = escape_html(name)
    
    # Add emoji based on type
    emoji_map = {
        'start': '🏠',
        'end': '👋',
        'menu': '📋',
        'message': '💬',
        'collect_input': '✍️',
        'collect_data': '✍️',
        'question': '❓',
        'action': '⚡',
        'process': '⚡',
        'condition': '🔀',
        'api_call': '🌐',
        'jump': '↗️',
        'validation': '✅'
    }
    
    emoji = emoji_map.get(node_type, '📌')
    
    # Build label with HTML-like formatting
    label = f'<<TABLE BORDER="0" CELLBORDER="0" CELLSPACING="0">'
    label += f'<TR><TD><B>{emoji} {name}</B></TD></TR>'
    label += f'<TR><TD><FONT POINT-SIZE="10" COLOR="gray">{node_type}</FONT></TD></TR>'
    
    # Add message preview if available
    if 'message' in node and node['message']:
        msg_preview = truncate_text(node['message'].split('\n')[0], 35)
        msg_preview = escape_html(msg_preview)
        label += f'<TR><TD><FONT POINT-SIZE="9">{msg_preview}</FONT></TD></TR>'
    
    # Add options count for menu nodes
    if node_type == 'menu' and 'options' in node:
        options_count = len(node.get('options', []))
        label += f'<TR><TD><FONT POINT-SIZE="9" COLOR="blue">{options_count} options</FONT></TD></TR>'
    
    # Add validation info for collect_input/collect_data nodes
    if node_type in ['collect_input', 'collect_data'] and 'validation' in node:
        validation = node.get('validation', {})
        if validation.get('required'):
            label += f'<TR><TD><FONT POINT-SIZE="9" COLOR="red">Required</FONT></TD></TR>'
    
    label += '</TABLE>>'
    
    return label

def get_edge_label(transition: Dict, option: Optional[Dict] = None) -> str:
    """Create edge label from transition and option data."""
    labels = []
    
    # Add option label if available
    if option:
        opt_label = option.get('label', '')
        opt_value = option.get('value', '')
        if opt_label:
            labels.append(opt_label)
        elif opt_value:
            labels.append(str(opt_value))
    
    # Add transition label
    trans_label = transition.get('label', '')
    if trans_label and trans_label not in labels:
        labels.append(trans_label)
    
    # Add condition info
    condition = transition.get('condition', {})
    if condition:
        condition_type = condition.get('type', '')
        condition_value = condition.get('value', '')
        if condition_type and condition_value:
            labels.append(f"[{condition_type}: {condition_value}]")
    
    # Combine labels
    label = '\n'.join(labels) if labels else ''
    return truncate_text(label, 30)

def visualize_convo(convo_data: Dict, output_file: str = None, format: str = 'png'):
    """
    Visualize convo as a directed graph.
    
    Args:
        convo_data: convo JSON data
        output_file: Output file path (without extension)
        format: Output format (png, pdf, svg, etc.)
    """
    # Create directed graph
    dot = graphviz.Digraph(comment=convo_data.get('name', 'convo'))
    
    # Set graph attributes for better layout
    dot.attr(rankdir='TB')  # Top to Bottom layout
    dot.attr('node', fontname='Arial', fontsize='11')
    dot.attr('edge', fontname='Arial', fontsize='9')
    dot.attr(bgcolor='white')
    dot.attr(pad='0.5')
    dot.attr(nodesep='1.0')
    dot.attr(ranksep='1.2')
    dot.attr(splines='ortho')  # Orthogonal edges for cleaner look
    
    # Add title
    title = convo_data.get('name', 'convo Visualization')
    description = convo_data.get('description', '')
    dot.attr(label=f'{title}\n{description}', fontsize='16', labelloc='t')
    
    # Track all nodes and edges
    nodes_dict = {node['id']: node for node in convo_data.get('nodes', [])}
    edges_added: Set[tuple] = set()
    
    # Add nodes
    for node in convo_data.get('nodes', []):
        node_id = node['id']
        node_type = node.get('type', 'unknown')
        
        # Create node with styling
        dot.node(
            node_id,
            label=create_node_label(node),
            shape=get_node_shape(node_type),
            style='filled',
            fillcolor=get_node_color(node_type),
            color='black',
            fontcolor='white' if node_type in ['start', 'end'] else 'black',
            penwidth='2'
        )
    
    # Add edges (transitions)
    for node in convo_data.get('nodes', []):
        node_id = node['id']
        node_type = node.get('type', 'unknown')
        
        # For menu nodes, match transitions with options
        if node_type == 'menu':
            options = node.get('options', [])
            transitions = node.get('transitions', [])
            
            for idx, transition in enumerate(transitions):
                target_id = transition.get('target_node_id')
                if not target_id:
                    continue
                
                edge_key = (node_id, target_id, idx)
                if edge_key in edges_added:
                    continue
                
                # Find matching option
                option = None
                for opt in options:
                    if opt.get('value') == transition.get('condition', {}).get('value'):
                        option = opt
                        break
                
                # Create edge label
                label = get_edge_label(transition, option)
                
                # Add edge with styling
                edge_color = 'blue' if idx == 0 else 'gray'
                edge_style = 'solid'
                
                dot.edge(
                    node_id,
                    target_id,
                    label=label,
                    color=edge_color,
                    style=edge_style,
                    fontsize='9',
                    penwidth='1.5'
                )
                
                edges_added.add(edge_key)
        else:
            # Regular transitions
            for idx, transition in enumerate(node.get('transitions', [])):
                target_id = transition.get('target_node_id')
                if not target_id:
                    continue
                
                edge_key = (node_id, target_id, idx)
                if edge_key in edges_added:
                    continue
                
                # Create edge label
                label = get_edge_label(transition)
                
                # Add edge with styling
                edge_color = 'blue' if idx == 0 else 'gray'
                edge_style = 'solid' if idx == 0 else 'dashed'
                
                dot.edge(
                    node_id,
                    target_id,
                    label=label,
                    color=edge_color,
                    style=edge_style,
                    fontsize='9',
                    penwidth='1.5'
                )
                
                edges_added.add(edge_key)
        
        # Add default transition
        default_target = node.get('default_transition')
        if default_target:
            edge_key = (node_id, default_target, -1)
            if edge_key not in edges_added:
                dot.edge(
                    node_id,
                    default_target,
                    label='default',
                    color='red',
                    style='dotted',
                    fontsize='9',
                    penwidth='1.5'
                )
                edges_added.add(edge_key)
    
    # Generate output
    if output_file:
        output_path = Path(output_file)
        dot.render(str(output_path), format=format, cleanup=True)
        print(f"✅ Visualization saved to: {output_path}.{format}")
    else:
        # Auto-generate filename
        convo_id = convo_data.get('id', 'convo')
        output_path = Path(f'convo_visualization_{convo_id}')
        dot.render(str(output_path), format=format, cleanup=True)
        print(f"✅ Visualization saved to: {output_path}.{format}")
    
    return dot

def generate_statistics(convo_data: Dict):
    """Generate and print convo statistics."""
    nodes = convo_data.get('nodes', [])
    
    print("\n" + "="*60)
    print("📊 convo STATISTICS")
    print("="*60)
    
    print(f"\n🏷️  Name: {convo_data.get('name', 'N/A')}")
    print(f"🆔 ID: {convo_data.get('id', 'N/A')}")
    print(f"📝 Description: {convo_data.get('description', 'N/A')}")
    print(f"🚀 Start Node: {convo_data.get('start_node_id', 'N/A')}")
    print(f"⏱️  Timeout: {convo_data.get('timeout_minutes', 'N/A')} minutes")
    
    # Count nodes by type
    node_types = {}
    total_transitions = 0
    total_options = 0
    
    for node in nodes:
        node_type = node.get('type', 'unknown')
        node_types[node_type] = node_types.get(node_type, 0) + 1
        total_transitions += len(node.get('transitions', []))
        
        # Count menu options
        if node_type == 'menu':
            total_options += len(node.get('options', []))
    
    print(f"\n📦 Total Nodes: {len(nodes)}")
    print(f"🔀 Total Transitions: {total_transitions}")
    print(f"📋 Total Menu Options: {total_options}")
    
    print("\n📋 Nodes by Type:")
    for node_type, count in sorted(node_types.items()):
        print(f"   • {node_type}: {count}")
    
    # Find nodes with most transitions
    max_transitions = 0
    max_transition_nodes = []
    
    for node in nodes:
        transition_count = len(node.get('transitions', []))
        if transition_count > max_transitions:
            max_transitions = transition_count
            max_transition_nodes = [node['id']]
        elif transition_count == max_transitions and max_transitions > 0:
            max_transition_nodes.append(node['id'])
    
    if max_transition_nodes:
        print(f"\n🔝 Most Complex Nodes ({max_transitions} transitions):")
        for node_id in max_transition_nodes:
            node = next((n for n in nodes if n['id'] == node_id), None)
            node_name = node.get('name', node_id) if node else node_id
            print(f"   • {node_id} ({node_name})")
    
    # Find dead ends (nodes with no transitions)
    dead_ends = [node for node in nodes if not node.get('transitions') and node.get('type') != 'end']
    if dead_ends:
        print(f"\n⚠️  Dead End Nodes (no transitions):")
        for node in dead_ends:
            node_name = node.get('name', node['id'])
            print(f"   • {node['id']} ({node_name})")
    
    print("\n" + "="*60)

def main():
    """Main function."""
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("Usage: python visualize_convo.py <convo_json_file> [output_file] [format]")
        print("\nExample:")
        print("  python visualize_convo.py enhanced_customer_support_flow.json")
        print("  python visualize_convo.py enhanced_customer_support_flow.json output png")
        print("  python visualize_convo.py enhanced_customer_support_flow.json output svg")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    format = sys.argv[3] if len(sys.argv) > 3 else 'png'
    
    # Load convo data
    try:
        convo_data = load_convo(input_file)
    except FileNotFoundError:
        print(f"❌ Error: File '{input_file}' not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON in '{input_file}': {e}")
        sys.exit(1)
    
    # Generate visualization
    print("🔄 Generating convo visualization...")
    dot = visualize_convo(convo_data, output_file, format)
    
    # Generate statistics
    generate_statistics(convo_data)
    
    print("\n✅ Done!")

if __name__ == "__main__":
    main()
