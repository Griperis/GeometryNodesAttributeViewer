# Geonodes Attribute Viewer - view and debug geonodes attributes in scene 
# Author: Zdenek Dolezal
# Licence: GPL 3.0

# Some of the code is inspired by the awesome 'Node Wrangler' addon, thanks goes to the
# authors Bartek Skorupa, Greg Zaal, Sebastian Koenig, Christian Brinkmann, Florian Meyer

# Thanks to 'user3597862' for the code snipped used to implement 'mouse_to_region_coords' method
# https://blender.stackexchange.com/questions/218096/translate-area-mouse-coordinates-to-the-the-node-editors-blackboard-coordinates

bl_info = {
    "name": "Attribute Viewer",
    "author": "Zdenek Dolezal",
    "version": (1, 0, 0),
    "blender": (3, 3, 0),
    "location": "Node Editor N-panel or Ctrl-Shift-W",
    "description": "",
    "category": "Node",
}

import bpy
import math
import typing
import os


GEONODES_PATH = os.path.join("data", "attribute_viewer_nodes.blend") 

# Main data structure representing what name of nodegroup corresponds to what socket type.
# If there are more than one viewer for one type, then the default spawned one should be
# selectable from preferences.
VIEWER_NAMES = {
    "AV_Float-Value_AttributeViewer": bpy.types.NodeSocketFloat,
    "AV_Int-Value_AttributeViewer": bpy.types.NodeSocketInt,
    "AV_Vector-Value_AttributeViewer": bpy.types.NodeSocketVector,
    "AV_Vector_AttributeViewer": bpy.types.NodeSocketVector,
    "AV_Color-Value_AttributeViewer": bpy.types.NodeSocketColor,
    "AV_Color_AttributeViewer": bpy.types.NodeSocketColor,
}

# How to scale text when it is spawned (so it looks somewhat good)
GLOBAL_SCALE_FACTOR = 0.1


def get_readable_viewer_name(name: str):
    _, middle, _ = name.split("_")
    return middle.replace("-", " ")        


class Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__
    
    digits: bpy.props.IntProperty(
        name="Digits",
        default=6,
        min=0
    )
    decimals: bpy.props.IntProperty(
        name="Decimals",
        default=1,
        min=0,
    )

    base: bpy.props.FloatProperty(
        name="Base (2, 10, 16)",
        description="Use different base (upto 16 are supported). Convert to PI-base if you want :)",
        default=10,
        min=2,
        max=16
    )

    scale: bpy.props.FloatProperty(
        name="Text Scale",
        default=1,
        min=0
    )

    color: bpy.props.FloatVectorProperty(
        name="Color",
        subtype='COLOR',
        size=4,
        default=(0.799103, 0.337164, 0.006995, 1.0)
    )

    offset_along_normals: bpy.props.BoolProperty(
        name="Offset Along Normals",
        default=False,
    )
    offset: bpy.props.FloatVectorProperty(
        name="Offset",
        size=3,
        default=(0.0, 0.0, 0.0)
    )

    viewport_only: bpy.props.BoolProperty(
        name="Viewport Only",
        description="If toggled, then viewer geometry is shown only in viewport",
        default=True
    )
    show_geometry: bpy.props.BoolProperty(
        name="Show Original Geometry",
        description="If toggled, original geometry is output with the added geometry",
        default=True
    )

    collapse_default_settings: bpy.props.BoolProperty()

    default_color_viewer: bpy.props.EnumProperty(
        name="Default Color Viewer",
        description="What 'Color Viewer' to spawn when using 'ViewAttribute' operator",
        items=lambda self, _: self.get_default_viewer_enum_items(bpy.types.NodeSocketColor)
    )

    default_vector_viewer: bpy.props.EnumProperty(
        name="Default Vector Viewer",
        description="What 'Vector Viewer' to spawn when using 'ViewAttribute' operator",
        items=lambda self, _: self.get_default_viewer_enum_items(bpy.types.NodeSocketVector)
    )

    def get_default_viewer_enum_items(self, socket_type: typing.Type[bpy.types.NodeSocket]):
        ret = []
        for name, viewer_type in VIEWER_NAMES.items():
            if socket_type == viewer_type:
                readable_name = get_readable_viewer_name(name)
                ret.append((name, readable_name, readable_name))

        return ret 

    def get_viewer_name_for_socket_type(
        self,
        socket_type: typing.Type[bpy.types.NodeSocket]
    ) -> str:
        if socket_type == bpy.types.NodeSocketColor:
            return self.default_color_viewer
        elif socket_type == bpy.types.NodeSocketVector:
            return self.default_vector_viewer
        else:
            for name, viewer_socket_type in VIEWER_NAMES.items():
                if socket_type == viewer_socket_type:
                    return name

        raise ValueError(f"Unsupported socket type to view: {socket_type}")
            

    def draw(self, context: bpy.types.Context) -> None:
        layout: bpy.types.UILayout = self.layout
        row = layout.row()
        row.label(text="Default Viewers", icon='COMMUNITY')
        row = row.row()
        row.enabled = False
        row.alignment = 'LEFT'
        row.label(text="(What viewer to spawn when viewing automatically)")
        col = layout.column()
        col.prop(self, "default_vector_viewer")
        col.prop(self, "default_color_viewer")
        
        row = layout.row(align=True)
        icon = 'TRIA_RIGHT' if self.collapse_default_settings else 'TRIA_DOWN'
        row.prop(self, "collapse_default_settings", icon_only=True, icon=icon, emboss=False)
        row.label(text="Default Viewer Settings")
        row = row.row()
        row.enabled = False
        row.alignment = 'LEFT'
        row.label(text="(Automatically set properties for newly spawned viewers)")
        if not self.collapse_default_settings:
            col = layout.column()
            row = col.row()
            row.enabled = False
            row.label(text="Numbers")
            col.prop(self, "digits")
            col.prop(self, "decimals")
            col.prop(self, "base")
            col.separator()
            
            row = col.row()
            row.enabled = False
            row.label(text="Appearance") 
            col.prop(self, "scale")
            col.prop(self, "color")
            col.separator()
            col.prop(self, "offset_along_normals")
            col.prop(self, "offset")
            col.separator()
            col.prop(self, "viewport_only")
            col.prop(self, "show_geometry")

    def apply_defaults(self, node: bpy.types.GeometryNodeGroup) -> None:
        for prop_name in self.customizable_prop_defaults:
            for input_ in node.inputs:
                if prop_name == input_.name.lower():
                    input_.default_value = getattr(self, prop_name)
                    break 

    @property
    def customizable_prop_defaults(self):
        return [
            "digits",
            "decimals",
            "base",
            "scale",
            "color", 
            "offset_along_normals",
            "viewport_only",
            "show_geometry"
        ]


def get_preferences(context: typing.Optional[bpy.types.Context] = None) -> Preferences:
    if context is None:
        context = bpy.context

    return context.preferences.addons[__package__].preferences
    

def get_geonodes_path() -> str:
    return os.path.abspath(GEONODES_PATH)


def ensure_viewer_nodes_loaded(link: bool = True):
    with bpy.data.libraries.load(get_geonodes_path(), link=link) as (data_from, data_to):
        for node_group_name in VIEWER_NAMES:
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

        if isinstance(socket, tuple(VIEWER_NAMES.values())):
            yield socket


def is_viewer_node(node: bpy.types.Node) -> bool:
    if not isinstance(node, bpy.types.GeometryNodeGroup):
        return False
    
    assert hasattr(node, "node_tree")
    if node.node_tree is None:
        return False

    return node.node_tree.name.startswith(tuple(VIEWER_NAMES))


def is_socket_connected_to_viewer(
    node_tree: bpy.types.NodeTree, 
    from_socket: bpy.types.NodeSocket,
    check_geometry_socket: bool = False
) -> bool:
    """Returns True if 'from_socket' is already connected to 'Attribute' socket of viewer
    
    If 'check_geometry_socket' is True, then also 'Geometry' named socket is considered
    as valid connection.
    """
    to_socket_names = ("Attribute", "Geometry") if check_geometry_socket else ("Attribute")
    for link in node_tree.links:
        if link.from_socket == from_socket and \
            is_viewer_node(link.to_node) and \
            link.to_socket.name in to_socket_names:
            return True

    return False   


def find_attribute_viewer_nodes_for_socket(
    node_tree: bpy.types.NodeTree,
    socket: bpy.types.NodeSocket
) -> typing.List[bpy.types.GeometryNodeGroup]:
    ret = []
    searched_name = get_preferences().get_viewer_name_for_socket_type(type(socket))
    for node in node_tree.nodes:
        if not isinstance(node, bpy.types.GeometryNodeGroup):
            continue

        if hasattr(node, "node_tree") and searched_name in node.node_tree.name:
            ret.append(node)

    return ret


def find_attribute_viewer_nodes(
    node_tree: bpy.types.NodeTree
) -> typing.Iterable[bpy.types.GeometryNodeGroup]:
    for node in node_tree.nodes:
        if is_viewer_node(node):
            yield node


def new_node_group(node_tree: bpy.types.NodeTree, name: str) -> bpy.types.NodeCustomGroup:
    node = node_tree.nodes.new(type='GeometryNodeGroup')
    node_tree: bpy.types.GeometryNodeGroup = bpy.data.node_groups.get(name)
    node.node_tree = node_tree
    return node


def new_attribute_viewer_from_socket_type(
    node_tree: bpy.types.NodeTree,
    socket_type: typing.Type[bpy.types.NodeSocket]
) -> bpy.types.GeometryNodeGroup:
    node = new_node_group(node_tree, get_preferences().get_viewer_name_for_socket_type(socket_type))
    get_preferences().apply_defaults(node)
    return node


def new_attribute_viewer_from_name(
    node_tree: bpy.types.NodeTree,
    name: str
) -> bpy.types.GeometryNodeGroup:
    node = new_node_group(node_tree, name)
    get_preferences().apply_defaults(node)
    return node


def get_attribute_viewer(
    node_tree: bpy.types.NodeTree,
    socket: bpy.types.NodeSocket,
    reuse_nodes: bool = True
) -> typing.Tuple[bool, bpy.types.NodeCustomGroup]:
    # Connects 'socket' from 'node' in 'node_tree' to viewer node
    # and connects the viewer to output
    is_new = False
    attribute_viewers = find_attribute_viewer_nodes_for_socket(node_tree, socket)
    if not reuse_nodes or len(attribute_viewers) == 0:
        node_group = new_attribute_viewer_from_socket_type(node_tree, type(socket)) 
        is_new = True
    else:
        node_group = attribute_viewers[0]

    return is_new, node_group


def get_first_geometry_output(
    node: bpy.types.Node
) -> typing.Optional[bpy.types.NodeSocketGeometry]:
    for socket in node.outputs:
        if isinstance(socket, bpy.types.NodeSocketGeometry):
            return socket
    
    return None


def safe_get_active_object(context: bpy.types.Context) -> typing.Optional[bpy.types.Object]:
    if not hasattr(context, "active_object"):
        return None
    
    return context.active_object


def adjust_viewer_text_size(
    obj: typing.Optional[bpy.types.Object],
    viewer: bpy.types.GeometryNodeGroup
):
    size_factor = max(obj.dimensions)
    if obj is None or math.isclose(size_factor, 0.0) or size_factor < 0:
        size_factor = 1.0

    text_size = size_factor * GLOBAL_SCALE_FACTOR
    input: bpy.types.NodeSocketFloat = viewer.inputs.get("Scale")
    input.default_value = text_size


def mouse_to_region_coords(
    context: bpy.types.Context,
    event: bpy.types.Event
) -> typing.Tuple[float, float]:

    region = context.region.view2d  
    ui_scale = context.preferences.system.ui_scale     
    x, y = region.region_to_view(event.mouse_region_x, event.mouse_region_y)
    return (x / ui_scale, y / ui_scale)


class GeoNodesEditorOnlyMixin:
    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return context.space_data.type == 'NODE_EDITOR' and \
            context.space_data.node_tree is not None and \
            context.space_data.node_tree.type == 'GEOMETRY'


class AV_ViewAttribute(GeoNodesEditorOnlyMixin, bpy.types.Operator):
    bl_idname = "attribute_viewer.view"
    bl_label = "View Attribute"

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        space: bpy.types.SpaceNodeEditor = context.space_data
        node_tree = space.node_tree

        if ('FINISHED' in bpy.ops.node.select(location=(event.mouse_x, event.mouse_y))):
            active_node = node_tree.nodes.active
            if is_viewer_node(active_node):
                self.report({'WARNING'}, "Can't view attribute from itself!")
                return {'FINISHED'}

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

                # find geometry links connected to viewer
                prev_geometry_socket = None
                for link in list(node_tree.links):
                    if is_viewer_node(link.to_node) and \
                        isinstance(link.to_socket, bpy.types.NodeSocketGeometry):
                        prev_geometry_socket = link.from_socket
                        break

                # Disconnect other sockets going to viewer and connect this one
                prev_viewer_location = None
                for link in list(node_tree.links):
                    to_node = link.to_node
                    if link.from_socket in viewable_sockets and is_viewer_node(to_node):
                        prev_viewer_location = to_node.location
                        node_tree.links.remove(link)
                        # Also remove other viewers
                        node_tree.nodes.remove(to_node)

                socket_to_view = viewable_sockets[idx]
                is_new, attribute_viewer = get_attribute_viewer(node_tree, socket_to_view)
                if prev_geometry_socket:
                    node_tree.links.new(prev_geometry_socket, attribute_viewer.inputs[0])
                node_tree.links.new(socket_to_view, attribute_viewer.inputs[1])

                if prev_viewer_location:
                    attribute_viewer.location = prev_viewer_location
                elif is_new:
                    attribute_viewer.location = (active_node.location.x + 400, active_node.location.y) 
                
            geometry_socket = get_first_geometry_output(active_node)
            # Attribute viewer is connected to socket, but also has geometry socket that
            # could be connected and isn't
            if geometry_socket is not None:
                # Selected node doesn't have any valid sockets to preview, but we can still
                # switch the geometry input of the attribute viewer if there is any present
                if attribute_viewer is None:
                    all_attribute_viewers = list(find_attribute_viewer_nodes(node_tree))
                    if len(all_attribute_viewers) > 0:
                        attribute_viewer = all_attribute_viewers[0]

                    for viewer in all_attribute_viewers:
                        node_tree.links.new(geometry_socket, viewer.inputs[0])

            
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
                adjust_viewer_text_size(
                    safe_get_active_object(context),
                    attribute_viewer
                )
        
        return {'FINISHED'}


class AV_RemoveViewer(GeoNodesEditorOnlyMixin, bpy.types.Operator):
    bl_idname = "attribute_viewer.remove_viewer"
    bl_label = "Remove Attribute Viewer"

    nodes_to_remove = []
    links_to_remove = []

    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.label(text=f"Going to remove ({len(AV_RemoveViewer.nodes_to_remove)}) viewers "
            f"and ({len(AV_RemoveViewer.links_to_remove)}) links, OK?"
        )

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        space: bpy.types.SpaceNodeEditor = context.space_data
        node_tree = space.node_tree
        AV_RemoveViewer.nodes_to_remove.clear()
        AV_RemoveViewer.links_to_remove.clear()
        
        if ('FINISHED' in bpy.ops.node.select(location=(event.mouse_x, event.mouse_y))):
            active_node = node_tree.nodes.active
            viewer_connected_sockets = set()
            for socket in active_node.outputs:
                if is_socket_connected_to_viewer(node_tree, socket, check_geometry_socket=True):
                    viewer_connected_sockets.add(socket)

            for link in list(node_tree.links):
                if link.from_socket in viewer_connected_sockets and is_viewer_node(link.to_node):
                    self.nodes_to_remove.append(link.to_node)
                    self.links_to_remove.append(link)

            # Don't invoke prompt if there is simple case that is obvious
            if len(AV_RemoveViewer.nodes_to_remove) == 1 and \
                len(AV_RemoveViewer.nodes_to_remove) <= 2:
                for link in self.links_to_remove:
                    node_tree.links.remove(link)

                for node in self.nodes_to_remove:
                    node_tree.nodes.remove(node)
                
                return {'FINISHED'}
            
            if len(AV_RemoveViewer.nodes_to_remove) == 0 and \
                len(AV_RemoveViewer.links_to_remove) == 0:
                return {'FINISHED'}

            return context.window_manager.invoke_props_dialog(self)

        return {'FINISHED'}

    def execute(self, context: bpy.types.Context):
        space: bpy.types.SpaceNodeEditor = context.space_data
        node_tree = space.node_tree

        for link in AV_RemoveViewer.links_to_remove:
            node_tree.links.remove(link)

        for node in AV_RemoveViewer.nodes_to_remove:
            node_tree.nodes.remove(node)

        return {'FINISHED'}


class AV_AddViewer(GeoNodesEditorOnlyMixin, bpy.types.Operator):
    bl_idname = "attribute_viewer.add_viewer"
    bl_label = "Add Viewer"
    bl_description = "Adds viewer node group of your choice into active node tree"

    viewer_type: bpy.props.EnumProperty(
        name="Viewer Type",
        items=lambda _, __: AV_AddViewer.get_viewer_enum_items(),
    )

    @staticmethod
    def get_viewer_enum_items() -> typing.Iterable[typing.Tuple[str, str, str]]:
        enum_items = []
        for name in VIEWER_NAMES:
            readable_name = get_readable_viewer_name(name)
            enum_items.append((name, readable_name, readable_name))

        return enum_items

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.prop(self, "viewer_type")

    def invoke(self, context: bpy.types.Context, event: bpy.types.Event):
        self.mouse_position = mouse_to_region_coords(context, event)
        return self.execute(context)

    def execute(self, context: bpy.types.Context):
        space: bpy.types.SpaceNodeEditor = context.space_data
        node_tree = space.node_tree
        ensure_viewer_nodes_loaded()
        viewer = new_attribute_viewer_from_name(node_tree, self.viewer_type)
        viewer.location = self.mouse_position
        adjust_viewer_text_size(
            safe_get_active_object(context),
            viewer
        )

        # Deselect all nodes in order to not move them with following operator
        for node in node_tree.nodes:
            node.select = False

        viewer.select = True
        return bpy.ops.node.translate_attach_remove_on_cancel('INVOKE_DEFAULT')


class AV_RemoveAllViewers(GeoNodesEditorOnlyMixin, bpy.types.Operator):
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


class AV_QuickView(GeoNodesEditorOnlyMixin, bpy.types.Operator):
    bl_idname = "attribute_viewer.quick_view"
    # shown in context menu, alows easy view of UV_Map, VertexColor, ...
    # when clicked geometry node group is going to be spawned on the mesh
    # and connected with the correct attributes, ...
    # Use cases:
    # - vertex crease
    # - vertex color
    # - vertex position


class AV_AttributeMenu(GeoNodesEditorOnlyMixin, bpy.types.Menu):
    bl_idname = "NODE_MT_attribute_viewer_attribute_menu"
    bl_label = "Add Viewer"
    
    def draw(self, context: bpy.types.Context):
        layout = self.layout
        for type_, readable, _ in AV_AddViewer.get_viewer_enum_items():
            layout.operator(AV_AddViewer.bl_idname, text=readable).viewer_type = type_


class AV_MainMenu(GeoNodesEditorOnlyMixin, bpy.types.Menu):
    bl_idname = "NODE_MT_attribute_viewer_main_menu"
    bl_label = "Attribute Viewer"
    
    def draw(self, context: bpy.types.Context):
        layout = self.layout
        layout.operator_context = 'INVOKE_DEFAULT'
        layout.menu(AV_AttributeMenu.bl_idname, icon='ADD')
        layout.separator()
        layout.operator(AV_RemoveAllViewers.bl_idname, icon='PANEL_CLOSE')


class AV_Panel(GeoNodesEditorOnlyMixin, bpy.types.Panel):
    bl_idname = "NODE_PT_attribute_viewer"
    bl_label = "Attribute Viewer"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Attribute Viewer"

    def draw(self, context: bpy.types.Context):
        AV_MainMenu.draw(self, context)


# TODO: Change keymaps to not interfere with node wrangler :)
KEYMAP_DEFINITIONS = (
    (AV_ViewAttribute.bl_idname, 'MIDDLEMOUSE', 'PRESS', True, True, False, {}),
    (AV_RemoveViewer.bl_idname, 'RIGHTMOUSE', 'PRESS', True, True, False, {}),
    ("wm.call_menu", 'W', 'PRESS', True, True, False, {'name': AV_MainMenu.bl_idname})
)

CLASSES = [
    Preferences,
    # Operators
    AV_ViewAttribute,
    AV_AddViewer,
    AV_RemoveViewer,
    AV_RemoveAllViewers,
    # Panels
    AV_Panel,
    # Menu
    AV_AttributeMenu,
    AV_MainMenu,
]

REGISTERED_KEYMAPS = []


def register_keymaps():
    REGISTERED_KEYMAPS.clear()

    kc = bpy.context.window_manager.keyconfigs.addon
    if not kc:
        return
    
    keymap = kc.keymaps.new(name='Node Editor', space_type='NODE_EDITOR')
    for op, key, event, ctrl, shift, alt, props in KEYMAP_DEFINITIONS:
        keymap_item = keymap.keymap_items.new(op, key, event, ctrl=ctrl, shift=shift, alt=alt)
        if len(props) > 0:
            for prop, value in props.items():
                setattr(keymap_item.properties, prop, value)
    
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
