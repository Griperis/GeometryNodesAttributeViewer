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

GLOBAL_SCALE_FACTOR = 0.1

def get_geonodes_path() -> str:
    return os.path.abspath(GEONODES_PATH)


def ensure_viewer_nodes_loaded(link: bool = True):
    with bpy.data.libraries.load(get_geonodes_path(), link=link) as (data_from, data_to):
        for node_group_name in SOCKETS_NODE_NAME_MAP.values():
            if node_group_name in bpy.data.node_groups:
                # TODO: if linked and from library, then refresh
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


def find_first_attribute_viewer(
    node_tree: bpy.types.NodeTree
) -> typing.Optional[bpy.types.GeometryNodeGroup]:
    for node in node_tree.nodes:
        if not isinstance(node, bpy.types.GeometryNodeGroup):
            continue

        if node.node_tree.name.startswith(tuple(SOCKETS_NODE_NAME_MAP.values())):
            return node
    
    return None


def new_node_group(node_tree: bpy.types.NodeTree, name: str) -> bpy.types.NodeCustomGroup:
    node = node_tree.nodes.new(type='GeometryNodeGroup')
    node_tree: bpy.types.GeometryNodeGroup = bpy.data.node_groups.get(name)
    node.node_tree = node_tree
    return node


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
        node_group = new_node_group(node_tree, SOCKETS_NODE_NAME_MAP[type(socket)])
        is_new = True
    else:
        node_group = attribute_viewers[0]

    return is_new, node_group


def new_attribute_viewer(
    node_tree: bpy.types.NodeTree,
    socket_type: typing.Type[bpy.types.NodeSocket]
) -> bpy.types.GeometryNodeGroup:
    return new_node_group(node_tree, SOCKETS_NODE_NAME_MAP[socket_type])


def get_first_geometry_output(
    node: bpy.types.Node
) -> typing.Optional[bpy.types.NodeSocketGeometry]:
    for socket in node.outputs:
        if isinstance(socket, bpy.types.NodeSocketGeometry):
            return socket
    
    return None


def adjust_viewer_text_size(obj: bpy.types.Object, viewer: bpy.types.GeometryNodeGroup):
    text_size = max(obj.dimensions) * GLOBAL_SCALE_FACTOR
    input: bpy.types.NodeSocketFloat = viewer.inputs.get("Scale")
    input.default_value = text_size


class Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__


class GeoNodesEditorPoll:
    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.space_data.type == 'NODE_EDITOR' and \
            context.space_data.node_tree.type == 'GEOMETRY'


class AV_ViewAttribute(GeoNodesEditorPoll, bpy.types.Operator):
    bl_idname = "attribute_viewer.view"
    bl_label = "View Attribute"

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
            
            attribute_viewer = None
            if len(viewable_sockets) > 0:
                idx = viewer_connected_idx + 1
                if idx == len(viewable_sockets):
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
                
            geometry_socket = get_first_geometry_output(active_node)
            # Attribute viewer is connected to socket, but also has geometry socket that
            # could be connected and isn't
            if geometry_socket is not None:
                # Selected node doesn't have any valid sockets to preview, but we can still
                # switch the geometry input of the attribute viewer if there is any present
                if attribute_viewer is None:
                    attribute_viewer = find_first_attribute_viewer(node_tree)
                
                if attribute_viewer is not None:
                    node_tree.links.new(geometry_socket, attribute_viewer.inputs[0])

            
            # Connect attribute viewer to output
            if attribute_viewer is not None:
                output_node = None
                for node in node_tree.nodes:
                    if not isinstance(node, bpy.types.NodeGroupOutput):
                        continue

                    output_node = node
                    break
                

                if output_node is not None:
                    output_geo_socket = None
                    for socket in output_node.inputs:
                        if not isinstance(socket, bpy.types.NodeSocketGeometry):
                            continue
                        
                        output_geo_socket = socket
                        break
                    
                    join_geo_node = None
                    for link in node_tree.links:
                        if not isinstance(link.from_node, bpy.types.GeometryNodeJoinGeometry):
                            continue

                        if link.to_socket == output_geo_socket:
                            join_geo_node = link.from_node
                            break
                    
                    if join_geo_node is None:
                        join_geo_node = node_tree.nodes.new('GeometryNodeJoinGeometry')
                        join_geo_node.location = (output_node.location.x - 300, output_node.location.y) 
                    
                        for link in list(node_tree.links):
                            if link.to_socket == output_geo_socket:
                                node_tree.links.new(join_geo_node.inputs[0], link.from_socket)

                    found_link = None
                    for link in list(node_tree.links):
                        if link.to_node == join_geo_node and link.from_node == attribute_viewer:
                            found_link = link
                            break 
                    
                    if found_link is None:
                        node_tree.links.new(join_geo_node.inputs[0], attribute_viewer.outputs[0])
                    
                    node_tree.links.new(join_geo_node.outputs[0], output_geo_socket)

            if attribute_viewer is not None and context.active_object is not None:
                adjust_viewer_text_size(context.active_object, attribute_viewer)
            # TODO: 
            # - Auto-connect geometry input? (how to figure that out)
            # - - if has geometry output, use that one
            # - - if selected node has only geometry socket, reconnect only that one
            # - Auto-connect geometry output with join geometry of the group output
        
        return {'FINISHED'}


class AV_RemoveViewer(GeoNodesEditorPoll, bpy.types.Operator):
    bl_idname = "attribute_viewer.remove_viewer"
    bl_label = "Remove Attribute Viewer"

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


class AV_AddViewer(GeoNodesEditorPoll, bpy.types.Operator):
    bl_idname = "attribute_viewer.add_viewer"
    bl_label = "Add Viewer"
    bl_description = "Adds viewer node group of your choice into active node tree"

    viewer_type: bpy.props.EnumProperty(
        name="Viewer Type",
        items=lambda _, __: AV_AddViewer.get_viewer_enum_items()
    )

    @staticmethod
    def get_viewer_enum_items() -> typing.Iterable[typing.Tuple[str, str, str]]:
        enum_items = []
        for key, value in SOCKETS_NODE_NAME_MAP.items():
            readable_value = value[len("AV_"):-len("AttributeViewer")]
            enum_items.append((str(key), readable_value, readable_value))

        return enum_items

    @staticmethod
    def get_socket_type_from_enum_item(item: str) -> bpy.types.NodeSocket:
        for socket, _ in SOCKETS_NODE_NAME_MAP.items():
            if str(socket) == item:
                return socket

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "viewer_type")

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.mouse_position = (event.mouse_x, event.mouse_y)
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context):
        space: bpy.types.SpaceNodeEditor = context.space_data
        node_tree = space.node_tree
        selected_socket_type = AV_AddViewer.get_socket_type_from_enum_item(self.viewer_type)
        viewer = new_attribute_viewer(node_tree, selected_socket_type) 
        return {'FINISHED'}



class AV_RemoveAllViewers(GeoNodesEditorPoll, bpy.types.Operator):
    bl_idname = "attribute_viewer.remove_viewers"
    bl_label = "Remove All Viewers"
    bl_description = "Finds all viewers in active node_tree and removes them, doesn't preserve "
    "connections"

    def execute(self, context: bpy.types.Context):
        space: bpy.types.SpaceNodeEditor = context.space_data
        node_tree = space.node_tree
        for node in list(node_tree.nodes):
            if is_viewer_node(node):
                node_tree.nodes.remove(node)

        return {'FINISHED'}

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        return context.window_manager.invoke_confirm(self, event)


class AV_QuickView(GeoNodesEditorPoll, bpy.types.Operator):
    bl_idname = "attribute_viewer.quick_view"
    # shown in context menu, alows easy view of UV_Map, VertexColor, ...
    # when clicked geometry node group is going to be spawned on the mesh
    # and connected with the correct attributes, ...
    # Use cases:
    # - vertex crease
    # - vertex color
    # - vertex position


class AV_Panel(GeoNodesEditorPoll, bpy.types.Panel):
    bl_idname = "NODE_PT_attribute_visualiser"
    bl_label = "Attribute Visualiser"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Attribute Visualiser"

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.operator(AV_AddViewer.bl_idname)
        layout.operator(AV_RemoveAllViewers.bl_idname)


# TODO: Change keymaps to not interfere with node wrangler :)
KEYMAP_DEFINITIONS = (
    (AV_ViewAttribute.bl_idname, 'MIDDLEMOUSE', 'PRESS', True, True, False),
    (AV_RemoveViewer.bl_idname, 'RIGHTMOUSE', 'PRESS', True, True, False),
)

CLASSES = [
    Preferences,
    AV_ViewAttribute,
    AV_AddViewer,
    AV_RemoveViewer,
    AV_RemoveAllViewers,
    AV_Panel
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


    

