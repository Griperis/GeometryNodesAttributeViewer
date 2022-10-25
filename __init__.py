# Geonodes Attribute Viewer - view and debug geonodes attributes in scene 
# Author: Zdenek Dolezal
# Licence: GPL 3.0

# Some of the code is inspired by the awesome 'Node Wrangler' addon, thanks goes to the
# authors Bartek Skorupa, Greg Zaal, Sebastian Koenig, Christian Brinkmann, Florian Meyer

bl_info = {
    "name": "Attribute Viewer",
    "author": "Zdenek Dolezal",
    "version": (1, 0, 0),
    "blender": (3, 3, 0),
    "location": "Node Editor N-panel or Shift-V",
    "description": "",
    "category": "Node",
}

import bpy
import typing
import os


GEONODES_PATH = os.path.join("data", "attribute_viewer_nodes.blend") 

SOCKETS_NODE_NAME_MAP = {
    # bpy.types.NodeSocketBool: "AV_BoolAttributeViewer",
    bpy.types.NodeSocketFloat: "AV_FloatAttributeViewer",
    # bpy.types.NodeSocketInt: "AV_IntAttributeViewer",
    # bpy.types.NodeSocketVector: "AV_VectorAttributeViewer",
    # bpy.types.NodeSocketColor: "AV_ColorAttributeViewer",
}

def get_geonodes_path() -> str:
    return os.path.abspath(GEONODES_PATH)


def ensure_viewer_nodes_loaded(link: bool = True):
    with bpy.data.libraries.load(get_geonodes_path(), link=link) as (data_from, data_to):
        for node_group_name in SOCKETS_NODE_NAME_MAP.values():
            if node_group_name in bpy.data.node_groups:
                # if linked and from library, then refresh
                # if not linked, then link and use the linked one to
                ...
            else:
                assert node_group_name in data_from.node_groups
                data_to.node_groups.append(node_group_name)
                
def filter_applicable_sockets(
    node_outputs: typing.Iterable[bpy.types.NodeSocket]
) -> typing.Iterable[bpy.types.NodeSocket]:
    for socket in node_outputs:
        if socket.hide or not socket.enabled:
            continue

        if isinstance(socket, tuple(SOCKETS_NODE_NAME_MAP.keys())):
            yield socket


def is_viewer_node(node: bpy.types.Node) -> bool:
    if not isinstance(node, bpy.types.GeometryNodeGroup):
        return False
    
    assert hasattr(node, "node_tree")
    return node.node_tree.name.startswith(tuple(SOCKETS_NODE_NAME_MAP.values()))


def is_socket_connected_to_viewer(
    node_tree: bpy.types.NodeTree, 
    from_socket: bpy.types.NodeSocket,
) -> bool:
    """Returns True if 'from_socket' is already connected to 'attribute' socket of viewer"""
    viewer_name = SOCKETS_NODE_NAME_MAP[type(from_socket)]
    for link in node_tree.links:
        if not isinstance(link.to_node, bpy.types.GeometryNodeGroup):
            continue

        if link.from_socket == from_socket and viewer_name in link.to_node.node_tree.name and \
            link.to_socket.name == "Attribute":
            return True

    return False   


def find_attribute_viewer_nodes(
    node_tree: bpy.types.NodeTree,
    socket: bpy.types.NodeSocket
) -> typing.List[bpy.types.GeometryNodeGroup]:
    ret = []
    searched_name = SOCKETS_NODE_NAME_MAP[type(socket)]
    for node in node_tree.nodes:
        if not isinstance(node, bpy.types.GeometryNodeGroup):
            continue

        if hasattr(node, "node_tree") and searched_name in node.node_tree.name:
            ret.append(node)

    return ret


def get_attribute_viewer(
    node_tree: bpy.types.NodeTree,
    socket: bpy.types.NodeSocket,
    reuse_nodes: bool = True
) -> typing.Tuple[bool, bpy.types.NodeCustomGroup]:
    # Connects 'socket' from 'node' in 'node_tree' to viewer node
    # and connects the viewer to output
    is_new = False
    attribute_viewers = find_attribute_viewer_nodes(node_tree, socket)
    if not reuse_nodes or len(attribute_viewers) == 0:
        node_group = node_tree.nodes.new(type='GeometryNodeGroup')
        attribute_viewer: bpy.types.GeometryNodeGroup = bpy.data.node_groups.get(
            SOCKETS_NODE_NAME_MAP[type(socket)]) 
        node_group.node_tree = attribute_viewer
        is_new = True
    else:
        node_group = attribute_viewers[0]

    return is_new, node_group


class AV_ViewAttribute(bpy.types.Operator):
    bl_idname = "attribute_viewer.view"
    bl_label = "View Attribute"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.space_data.type == 'NODE_EDITOR' and \
            context.space_data.node_tree.type == 'GEOMETRY'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        space: bpy.types.SpaceNodeEditor = context.space_data
        node_tree = space.node_tree

        if ('FINISHED' in bpy.ops.node.select(location=(event.mouse_x, event.mouse_y))):
            active_node = node_tree.nodes.active
            ensure_viewer_nodes_loaded()
            # Connect active socket if any, or list through the sockets on click
            viewable_sockets = list(filter_applicable_sockets(active_node.outputs))
            viewer_connected_idx = -1
            for i, socket_to_view in enumerate(viewable_sockets):
                if is_socket_connected_to_viewer(node_tree, socket_to_view):
                    viewer_connected_idx = i
                    break

            idx = viewer_connected_idx + 1
            # No applicable socket to connect to
            if idx >= len(viewable_sockets):
                idx = 0

            # Disconnect other sockets going to viewer and connect this one
            for link in list(node_tree.links):
                if link.from_socket in viewable_sockets:
                    node_tree.links.remove(link)

            socket_to_view = viewable_sockets[idx]
            is_new, attribute_viewer = get_attribute_viewer(node_tree, socket_to_view)
            node_tree.links.new(socket_to_view, attribute_viewer.inputs[1])

            # adjust attribute viewer location
            if is_new:
                attribute_viewer.location = (active_node.location.x + 400, active_node.location.y) 
            
            # TODO: 
            # - Auto-connect geometry input? (how to figure that out)
            # - - if has geometry output, use that one
            # - Auto-connect geometry output with join geometry of the group output
        
        return {'FINISHED'}


class AV_RemoveViewer(bpy.types.Operator):
    bl_idname = "attribute_viewer.remove_viewer"
    bl_label = "View Attribute"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.space_data.type == 'NODE_EDITOR'

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        space: bpy.types.SpaceNodeEditor = context.space_data
        node_tree = space.node_tree
        
        if ('FINISHED' in bpy.ops.node.select(location=(event.mouse_x, event.mouse_y))):
            active_node = node_tree.nodes.active
            viewable_sockets = list(filter_applicable_sockets(active_node.outputs))
            viewer_connected_sockets = set()
            for socket in viewable_sockets:
                if is_socket_connected_to_viewer(node_tree, socket):
                    viewer_connected_sockets.add(socket)

            nodes_to_remove = []
            for link in list(node_tree.links):
                if link.from_socket in viewer_connected_sockets and is_viewer_node(link.to_node):
                    nodes_to_remove.append(link.to_node)
                    node_tree.links.remove(link)

            for node in nodes_to_remove:
                node_tree.nodes.remove(node)


        return {'FINISHED'}
            
            

KEYMAP_DEFINITIONS = (
    (AV_ViewAttribute.bl_idname, 'MIDDLEMOUSE', 'PRESS', True, True, False),
    (AV_RemoveViewer.bl_idname, 'RIGHTMOUSE', 'PRESS', True, True, False),
)

CLASSES = [
    AV_ViewAttribute,
    AV_RemoveViewer
]

REGISTERED_KEYMAPS = []


def register_keymaps():
    REGISTERED_KEYMAPS.clear()

    kc = bpy.context.window_manager.keyconfigs.addon
    if not kc:
        return
    
    keymap = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
    for op, key, event, ctrl, shift, alt in KEYMAP_DEFINITIONS:
        keymap_item = keymap.keymap_items.new(op, key, event, ctrl=ctrl, shift=shift, alt=alt)
        REGISTERED_KEYMAPS.append((keymap, keymap_item))


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)

    register_keymaps()


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

    for keymap, keymap_item in REGISTERED_KEYMAPS:
        keymap.keymap_items.remove(keymap_item)
    
    REGISTERED_KEYMAPS.clear()


    

