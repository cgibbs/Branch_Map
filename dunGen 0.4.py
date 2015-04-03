import libtcodpy as libtcod
import math
import Queue
import random

import time

SCREEN_WIDTH = 160
SCREEN_HEIGHT = 86

MAP_WIDTH = 160
MAP_HEIGHT = 86

CAMERA_WIDTH = 160
CAMERA_HEIGHT = 86

ROOM_MAX_SIZE = 3
ROOM_MIN_SIZE = 3
#MAX_ROOMS = 30
ROOM_SPACE = ROOM_MAX_SIZE + 1

FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10
FOG_TORCH_RADIUS = 4

NORTH = 0
EAST = 1
SOUTH = 2
WEST = 3

DIRECTIONS = [NORTH, EAST, SOUTH, WEST]

libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'Branch Test', False)                        
con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)

color_dark_wall     = libtcod.Color(  0,   0, 100)
color_light_wall    = libtcod.Color(130, 110,  50)
color_dark_ground   = libtcod.Color( 50,  50, 150)
color_light_ground  = libtcod.Color(200, 180,  50)

class Object:
    def __init__(self, x, y, char, name, color, hunger_dec=1, hunger=100, blocks=False,
                 always_visible=False, fighter=None, ai=None, equipment=None, item=None,
                 inv=None, mod_set=None, mod_name=None):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.hunger_dec = hunger_dec
        self.hunger = hunger
        self.blocks = blocks
        self.always_visible = always_visible
        self.inv = inv
        self.spec = ''
        self.mod_name=mod_name # Strong, Weak, Electric, etc.

        # components, owned by the Object, which allow special behaviors

        self.fighter = fighter
        if self.fighter: # let the fighter component know who owns it
            self.fighter.owner = self

        self.ai = ai
        if self.ai: # let the ai component know who owns it
            self.ai.owner = self

        self.item = item
        if self.item: # let the item component know who owns it
            self.item.owner = self

        self.equipment = equipment
        if self.equipment: # let the equipment component know what owns it
            self.equipment.owner = self
            self.item = Item() # a piece of equipment is always an Item (can be picked up and used)
            self.item.owner = self

        self.mod_set = mod_set # holds mods for object
        if self.mod_set is None:
            self.mod_set = set()

    def move(self, dx, dy):
        if ((0 <= (self.x + dx) < MAP_WIDTH) and (0 < (self.y + dy) < MAP_HEIGHT) 
            and not is_blocked(self.x + dx, self.y + dy)):
            self.x += dx
            self.y += dy
        elif (0 <= (self.x + dx) < MAP_WIDTH) and not is_blocked(self.x + dx, self.y):
            self.x += dx
        elif (0 <= (self.y + dy) < MAP_HEIGHT) and not is_blocked(self.x, self.y + dy):
            self.y += dy
        if self is not player and 'puddle' in map[self.x][self.y].mod_set:
            message("You hear splashing.", color_puddle)

    def move_towards(self, target_x, target_y):
        # vector from this object to target, and distance
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # normalize it to length 1 (keeping direction), then round it and
        # convert to integer for map grid movement
        dx = dx / distance
        dy = dy / distance
        if dx < 0:
            dx = int(0 - math.ceil(abs(dx)))
        else:
            dx = int(math.ceil(dx))
        if dy < 0:
            dy = int(0 - math.ceil(abs(dy)))
        else:
            dy = int(math.ceil(dy))
        self.move(dx, dy)

    def distance(self, x, y):
        # return distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

    def distance_to(self, other):
        # return distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def clear(self):
        libtcod.console_put_char(con, self.x-camera.x, self.y-camera.y, ' ', 
            libtcod.BKGND_NONE)

    def send_to_back(self):
        # sets drawing order such that this object is drawn underneath other stuff
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def check_floor(self):
        # mod_set on objects holds resistances as the same value for Tile's mod_set
        tile = map[self.x][self.y]
        for mod in tile.mod_set:
            if mod not in self.mod_set:
                pass # TODO: handle damages, maybe as a list 
                     #(for multiple damage types on floors)

    @property
    def full_name(self):
        if self.mod_name is not None:
            return self.mod_name + ' ' + self.name
        else:
            return self.name

class Player(Object):
    def move(self, dx, dy):
        global camera
        if ((0 <= (self.x + dx) < MAP_WIDTH) and (0 < (self.y + dy) < MAP_HEIGHT) 
            and not is_blocked(self.x + dx, self.y + dy)):
            self.x += dx
            self.y += dy
        elif (0 <= (self.x + dx) < MAP_WIDTH) and not is_blocked(self.x + dx, self.y):
            self.x += dx
        elif (0 <= (self.y + dy) < MAP_HEIGHT) and not is_blocked(self.x, self.y + dy):
            self.y += dy
        camera.move_to(player.x, player.y)


class Tile:
    def __init__(self, blocked, x, y, block_sight=None):
        # takes a set for modSet, and it determines the properties of a tile
        self.blocked = blocked
        self.explored = False
        self.x = x
        self.y = y
        self.h = 0        # for use with A*
        self.parent = None
        self.mod_set = set()

        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight
        
    def add_mod(self, mod):
        self.mod_set.add(mod)

class Camera:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = CAMERA_WIDTH
        self.height = CAMERA_HEIGHT

    def fix_camera(self):
        if self.x < 0:
            self.x = 0
        elif self.x > (MAP_WIDTH - CAMERA_WIDTH):
            self.x = MAP_WIDTH - CAMERA_WIDTH
        if self.y < 0:
            self.y = 0
        elif self.y > (MAP_HEIGHT - CAMERA_HEIGHT):
            self.y = MAP_HEIGHT - CAMERA_HEIGHT

    def move_to(self, x, y):
        # moves camera to center on (x, y)
        self.x = x - CAMERA_WIDTH/2
        self.y = y - CAMERA_HEIGHT/2
        self.fix_camera()

def handle_keys():
    global fov_recompute, keys, mouse, msg_index, game_msgs
    
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())    
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'

    if game_state == 'playing':
        if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
        	player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1,1)
        elif key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1,1)
        elif key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1,-1)
        elif key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1,-1)
        elif key.vk == libtcod.KEY_KP5: # wait
            pass

def render_all():
    global fov_map, color_dark_wall, color_light_wall, color_dark_ground, color_light_ground
    global fov_recompute, hunger, msg_index

    x_range = range(camera.x, camera.x + CAMERA_WIDTH)
    y_range = range(camera.y, camera.y + CAMERA_HEIGHT)

    if fov_recompute:
        # recompute FOV if need be (player movement or whatever)
        fov_recompute = False
        if 'fog' in map[player.x][player.y].mod_set:
            libtcod.map_compute_fov(fov_map, player.x, player.y, FOG_TORCH_RADIUS, 
                FOV_LIGHT_WALLS, FOV_ALGO)
        else:
            libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        for y in y_range:
            for x in x_range:
                # uncomment this to return to exploration mode
                #visible = libtcod.map_is_in_fov(fov_map, x, y)
                visible = True
                wall = map[x][y].block_sight
                mods = map[x][y].mod_set
                if not visible:
                    if map[x][y].explored:
                        if wall:
                            libtcod.console_set_char_background(con, x-camera.x, y-camera.y, 
                                color_dark_wall, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_char_background(con, x-camera.x, y-camera.y, 
                                color_dark_ground, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x-camera.x, y-camera.y, libtcod.black, 
                            libtcod.BKGND_SET)
                else:
                    if wall:
                        #libtcod.console_set_default_foreground(con, libtcod.white)
                        libtcod.console_set_char_background(con, x-camera.x, y-camera.y, 
                            color_light_wall, libtcod.BKGND_SET)
                        
                    else:
                        # THIS ELIF IS FOR A DEBUG COLOR
                        if map[x][y].h == 1:
                            libtcod.console_set_char_background(con, x-camera.x, y-camera.y, 
                                color_blood, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_char_background(con, x-camera.x, y-camera.y, 
                                color_light_ground, libtcod.BKGND_SET)
                    map[x][y].explored = True

    for obj in objects: # prevents drawing over the player
        if obj != player and (obj.x in x_range) and (obj.y in y_range):            
            libtcod.console_set_default_foreground(con, obj.color)
            libtcod.console_put_char(con, obj.x-camera.x, obj.y-camera.y, obj.char, 
                libtcod.BKGND_NONE)
       
    libtcod.console_set_default_foreground(con, player.color)
    libtcod.console_put_char(con, player.x-camera.x, player.y-camera.y, player.char, libtcod.BKGND_NONE)

    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

def make_map(secret):
    global map, objects, stairs, dungeon_level, camera

    secret = insert_spaces(secret)

    stack = []

    old_dir = EAST # initializes to EAST because that's where

    objects = [player]

    map = [[Tile(True, x, y)
            for y in range(MAP_HEIGHT) ]
           for x in range(MAP_WIDTH) ]

    rooms = []
    num_rooms = 0

    w = h = ROOM_MAX_SIZE
    x = MAP_WIDTH / 2
    y = MAP_HEIGHT / 2
        
    new_room = Rect(x,y,w,h)
    new_room.create()

    center_x, center_y = new_room.center()

    (new_x, new_y) = (x + ROOM_SPACE, y)

    player.x, player.y = new_room.center()
    camera.move_to(player.x, player.y)

    objects.append(Object(center_x, center_y, secret[num_rooms], 
        secret[num_rooms], libtcod.white))

    num_rooms += 1
        
    new_room = Rect(new_x, new_y,w,h)
    new_room.create()

    center_x, center_y = new_room.center()

    objects.append(Object(center_x, center_y, secret[num_rooms], 
        secret[num_rooms], libtcod.white))

    stack.append((new_room, (old_dir + 2) % 4)) # stores the reverse of the direction
    num_rooms += 1

    # tunnel to previous room
    map[center_x - 2][center_y].blocked = False
    map[center_x - 2][center_y].block_sight = False

    i = 0
    while (i < 10000) and (num_rooms < len(secret)) and (len(stack) != 0):
        if len(stack) > (len(secret) / 2):
            for i in range(0, random.randint(0, (len(secret) / 2) - 1)):
                stack.pop()
            # this looks scary, but it basically pops until it finds a spot to branch in
            # the same direction as old_dir

        (old_room, old_dir) = stack[len(stack) - 1] # peek at top of stack
        
        (new_x, new_y) = (old_room.x1, old_room.y1)

        temp_dirs = check_dirs_counterclock(old_room, old_dir)
        
        if len(temp_dirs) == 0:
            stack.pop()
            continue
        temp_dirs.append(temp_dirs[len(temp_dirs) - 1]) # slight bias toward last item, more likely to 
                                        # generate a "fuller" map

        i = random.choice(temp_dirs)

        if i == NORTH:
            new_y -= ROOM_SPACE
        if i == SOUTH:
            new_y += ROOM_SPACE
        if i == WEST:
            new_x -= ROOM_SPACE
        if i == EAST:
            new_x += ROOM_SPACE

        new_room = Rect(new_x, new_y, w, h) 
        new_room.create()

        center_x, center_y = new_room.center()

        # create tunnel to previous room
        if i == NORTH:
            map[center_x][center_y + 2].blocked = False 
            map[center_x][center_y + 2].block_sight = False
        if i == SOUTH:
            map[center_x][center_y - 2].blocked = False
            map[center_x][center_y - 2].block_sight = False
        if i == WEST:
            map[center_x + 2][center_y].blocked = False
            map[center_x + 2][center_y].block_sight = False
        if i == EAST:
            map[center_x - 2][center_y].blocked = False
            map[center_x - 2][center_y].block_sight = False

        objects.append(Object(center_x, center_y, secret[num_rooms], 
            secret[num_rooms], libtcod.white))

        stack.append((new_room, (i + 2) % 4))
        num_rooms += 1

    stairs = Object(center_x, center_y, '>', 'stairs', libtcod.white, always_visible=True)
    objects.append(stairs)
    stairs.send_to_back() # drawn below monsters

    if num_rooms < len(secret) - 1:
        make_map(secret)
        return True

    return False

class Rect:
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return(center_x, center_y)

    def intersect(self):
        # returns true if this rectangle intersects with another one
        for x in range(self.x1, self.x2 + 1):
            for y in range(self.y1, self.y2 + 1):
                if not map[x][y].blocked:
                    return True
        return False

    def create(self):
        global map
        for x in range(self.x1, self.x2):
            for y in range(self.y1, self.y2):
                map[x][y].blocked = False
                map[x][y].block_sight = False

def is_blocked(x, y):
    if map[x][y].blocked:
        return True

    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True

    return False

def check_dirs_counterclock(room, d):
    # check open directions counter-clockwise
    temp_dirs = []
    (new_x, new_y) = (room.x1, room.y1)

    t_d = (d - 1) % 4
    while t_d != d:
        if t_d == NORTH:
            if (0 < new_y - ROOM_SPACE < MAP_HEIGHT) and map[new_x][new_y - ROOM_SPACE].blocked:
                temp_dirs.append(NORTH)
            else:
                break
        if t_d == EAST:
            if (0 < new_x + ROOM_SPACE < MAP_WIDTH) and map[new_x + ROOM_SPACE][new_y].blocked:
                temp_dirs.append(EAST)
            else:
                break
        if t_d == SOUTH:
            if (0 < new_y + ROOM_SPACE < MAP_HEIGHT) and  map[new_x][new_y + ROOM_MAX_SIZE + 1].blocked:
                temp_dirs.append(SOUTH)
            else:
                break
        if t_d == WEST:
            if (0 < new_x - ROOM_SPACE < MAP_WIDTH) and map[new_x - ROOM_MAX_SIZE - 1][new_y].blocked:
                temp_dirs.append(WEST)
            else:
                break
        t_d = (t_d - 1) % 4
    return temp_dirs

def check_dirs_clock(room, d):
    # check open directions counter-clockwise
    temp_dirs = []
    (new_x, new_y) = (room.x1, room.y1)

    t_d = (d - 1) % 4
    while t_d != d:
        if t_d == NORTH:
            if map[new_x][new_y - ROOM_MAX_SIZE - 1].blocked:
                temp_dirs.append(NORTH)
        if t_d == EAST:
            if map[new_x + ROOM_MAX_SIZE + 1][new_y].blocked:
                temp_dirs.append(EAST)
        if t_d == SOUTH:
            if map[new_x][new_y + ROOM_MAX_SIZE + 1].blocked:
                temp_dirs.append(SOUTH)
        if t_d == WEST:
            if map[new_x - ROOM_MAX_SIZE - 1][new_y].blocked:
                temp_dirs.append(WEST)
        t_d = (t_d - 1) % 4
    return temp_dirs

def place_objects(room):
    # max number of monsters per room
    max_monsters = from_dungeon_level([[2,1], [3,4], [5,6], [1,10]])
    
    # spawn monsters
    num_monsters = libtcod.random_get_int(0, 0, max_monsters)
    for i in range(num_monsters):
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

        if not is_blocked(x, y):
            monster = create_monster(x, y)
            objects.append(monster)

    # maximum number of items per room
    max_items = from_dungeon_level([[1,1], [2,4]])

    # spawn items
    num_items = libtcod.random_get_int(0,0, max_items)
    for i in range(num_items):
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)
        if not is_blocked(x,y):
            item = create_item(x, y)
            objects.append(item)
            item.send_to_back()

    # maximum number of food items per room
    max_food = max_items     # just for now, for the sake of tweaking
    
    # spawn food
    num_food = libtcod.random_get_int(0, 0, max_food)
    for i in range(num_items):
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

        if not is_blocked(x,y):
            food = create_food(x, y)                
            objects.append(food)
            food.send_to_back()

def create_monster(x, y):
    # chance of each monster (figure out a better way to handle boss frequency)
    monster_chances = ['orc', 'mimic', 'skeleton', 'troll', 'lich', 'dragon',
                        'boss_dragon']
    
    choice = random.choice(monster_chances)

    if choice == 'orc':
        monster = Object(x, y, 'O', 'Orc', libtcod.desaturated_green,
                         blocks=True)
    elif choice == 'skeleton':
        monster = Object(x, y, 'S', 'Skeleton', libtcod.grey,
                         blocks=True)
    elif choice == 'mimic':
        monster = Object(x, y, item.char, item.full_name, item.color,
                         blocks=True)
    elif choice == 'troll':
        monster = Object(x, y, 'T', 'Troll', libtcod.darker_green,
                         blocks=True)
    elif choice == 'lich':
        monster = Object(x, y, 'L', 'Lich', libtcod.desaturated_blue,
                         blocks=True)
    elif choice == 'dragon':
        monster = Object(x, y, 'D', 'Dragon', libtcod.desaturated_red,
                         blocks=True) 
    elif choice == 'boss_dragon':
        monster = Object(x, y, 'D', 'Dragon', libtcod.desaturated_red,
                         blocks=True)
    return monster


def create_equip(x, y):
    # chance of each item (default is 0 at level 1, goes up after)
    item_chances = ['sword', 'shield']
    
    choice = random.choice(item_chances)
    
    if choice == 'sword':
        equipment_component = Weapon(slot='hand', power_bonus=2, attack_dice=(1,8))
        item = Object(x, y, '/', 'sword', libtcod.sky, equipment=equipment_component)
    elif choice == 'shield':
        equipment_component = Weapon(slot='hand', defense_bonus=1, attack_dice=(0,0))
        item = Object(x, y, '[', 'shield', libtcod.sky, equipment=equipment_component)

    return item

def create_item(x, y):
    # chance of each item (default is 0 at level 1, goes up after)
    item_chances = ['heal_lesser', 'heal', 'heal_greater', 'confuse', 'lightning',
                    'fireball', 'push', 'ice_wall', 'tome_heal_lesser', 'tome_heal',
                    'tome_heal_greater']
    
    choice = random.choice(item_chances)
    
    if choice == 'heal_lesser':
        item = Object(x, y, '!', 'lesser healing potion', libtcod.violet)
    elif choice == 'heal':
        item = Object(x, y, '!', 'healing potion', libtcod.violet)
    elif choice == 'heal_greater':
        item = Object(x, y, '!', 'greater healing potion', libtcod.violet)
    elif choice == 'tome_heal_lesser':
        item = Object(x, y, '=', 'tome of lesser healing', libtcod.blue)
    elif choice == 'tome_heal':
        item = Object(x, y, '=', 'tome of healing', libtcod.blue)
    elif choice == 'tome_heal_greater':
        item = Object(x, y, '=', 'tome of greater healing', libtcod.blue)
    elif choice == 'lightning':
        item = Object(x, y, '#', 'scroll of lightning bolt', libtcod.light_yellowt)
    elif choice == 'confuse':
        item = Object(x, y, '#', 'scroll of confusion', libtcod.light_yellow)
    elif choice == 'fireball':
        item = Object(x, y, '#', 'scroll of fireball', libtcod.light_yellow)
    elif choice == 'push':
        item = Object(x, y, '#', 'scroll of push', libtcod.light_yellow)
    elif choice == 'ice_wall':
        item = Object(x, y, '#', 'scroll of ice wall', libtcod.light_yellow)

    return item

def create_food(x, y):
    # chance of each food item
    food_chances = ['apple', 'coconut_bar', 'peanut_butter_bar', 'jellybeans',
                    'licorice_pastels', 'chocolate_morsels', 'spam', 
                    'sandwich', 'roast_beef']

    choice = random.choice(food_chances)
    
    if choice == 'apple':
        food = Object(x, y, 'a', 'apple', libtcod.light_pink)
    elif choice == 'coconut_bar':
        food = Object(x, y, 'c', 'coconut bar', libtcod.light_pink)
    elif choice == 'peanut_butter_bar':
        food = Object(x, y, 'c', 'peanut butter bar', libtcod.light_pink)
    elif choice == 'jellybeans':
        food = Object(x, y, 'c', 'jellybeans', libtcod.light_pink)
    elif choice == 'licorice_pastels':
        food = Object(x, y, 'c', 'licorice pastels', libtcod.light_pink)
    elif choice == 'chocolate_morsels':
        food = Object(x, y, 'c', 'chocolate morsels', libtcod.light_pink)
    elif choice == 'spam':
        food = Object(x, y, 'p', 'can of spam', libtcod.light_pink)
    elif choice == 'sandwich':
        food = Object(x, y, 's', 'sandwich', libtcod.light_pink)
    else:
        food = Object(x, y, 'r', 'roast beef', libtcod.light_pink)

    return food

def player_move_or_attack(dx, dy):
    global fov_recompute
    
    x = player.x + dx
    y = player.y + dy
    
    player.move(dx,dy)
    fov_recompute = True

def insert_spaces(s):
    s = list(s)
    for i in xrange(len(s)-1):
        while random.randrange(2):
            s[i] = s[i] + ' '
    return ''.join(s)

def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level, steps, hunger_msg, ice_counter
    global msg_index, camera
    msg_index = 0

    name = 'Player'

    inventory = []
    game_msgs = []

    libtcod.console_flush()

    player = Player(0, 0, '@', name, libtcod.white, blocks=True, fighter=None)


    player.spec = 'Swordsman'

    player.level = 1
    player.inv = inventory

    hunger_msg = False
    steps = 0

    ice_counter = None

    dungeon_level = 1
    camera = Camera(0, 0)
    make_map("I would like to fly a plane one day. The wind in my hair gives me hope. When the sun sets over the clouds, I know that everything will be okay.")
    initialize_fov()

    game_state = 'playing'

def initialize_fov():
    libtcod.console_clear(con)
    global fov_recompute, fov_map
    fov_recompute = True

    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight,
                                       not map[x][y].blocked)

def play_game():
    global key, mouse, msg_index

    player_action = None

    mouse = libtcod.Mouse()
    key = libtcod.Key()


    while not libtcod.console_is_window_closed():
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        
        render_all()
        libtcod.console_flush()

        for obj in objects:
            obj.clear()
        
        player_action = handle_keys()
        
        if player_action == 'exit':
            break


# ---------- Program ----------

new_game()
play_game()
