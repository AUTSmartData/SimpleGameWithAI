
import ai
import mapobject
import settings
import world
import worldmap

# For Key
import pygtk_chart
import pygtk_chart.bar_chart

import cairo
import glib
import glob
import gobject
import gtk
import json
import traceback
import sys
import time
import traceback

gtk.gdk.threads_init()
from threading import Thread, RLock
import multiprocessing
import Queue

import logging
log = logging.getLogger("GUI")

BUFFER_SIZE=100

import pango
AI_FONT = pango.FontDescription('Sans 10')


AI_STATS=[
  'moving',
  'shooting',
  'capturing',
  'idle',
  'kills',
  'units'
  ]

AI_STAT_COLORS={
  'bldgs'          : (0.0,0.5,0.0),
  'moving'         : (0.0,0.5,0.0),
  'shooting'       : (0.5,0.0,0.0),
  'capturing'      : (0.0,0.0,0.5),
  'idle'           : (0.5,0.5,0.5),
  'kills'          : (0.5,0.0,0.0),
  'units'          : (0.0,0.0,0.5),
  }

class MapGUI:
    def __init__(self):
        # Initialize Widgets

        self.initialize_map_window()
        # Initialize the world
        self.world = world.World()
        self.ai_drawables = {}
        self.colors = {}
        self.guiTurn = 0

        # Initialize our pixbuf queue
        self.stopped = False
        self.frame_queue = multiprocessing.Queue(BUFFER_SIZE)
        self.lock = RLock()

        self.processes = []

    def initialize_map_window(self):
        self.window = gtk.Window()
        box = gtk.HBox()
        self.key_area = gtk.VBox()
        key_outer = gtk.ScrolledWindow()
        key_outer.add_with_viewport(self.key_area)
        key_outer.set_size_request(200, -1)

        screen = gtk.gdk.screen_get_default()
        self.drawSize = min(screen.get_width(), screen.get_height())
        box.pack_end(key_outer, False)


        self.map_area = gtk.DrawingArea()

        box.pack_start(self.map_area, True)
        self.window.add(box)
        self.window.show_all()
        self.map_area.connect("expose-event", self.map_expose_event_cb)
        self.window.resize(700, 500)
        self.window.connect("destroy", end_threads)


    def draw_key_data(self):
        pass


    def add_ai(self, ai_class):
        a = self.world.addAI(ai_class)
        ai.generate_ai_color(a)

        vbox = gtk.VBox()
        label_box = gtk.HBox()
        label_color_box = gtk.EventBox()
        label = gtk.Label(str(ai_class).split(".")[-1])
        label_color_box.set_size_request(20, -1)
        label_color_box.modify_bg(gtk.STATE_NORMAL,
          gtk.gdk.Color(*ai.AI_COLORS[a.team]))
        label_box.pack_start(label_color_box, False)
        label_box.pack_start(label)
        label_box.set_size_request(-1, 20)

        vbox.pack_start(label_box, False)
        labels = {}
        hbox = gtk.HBox()
        vbox.pack_start(hbox, False)
        for stat in ['moving', 'shooting', 'capturing', 'idle']:
          labels[stat] = gtk.Label("%s: 0" % (stat))
          hbox.pack_start(labels[stat])

        kill_label = gtk.Label("kills: 0")
        vbox.pack_start(kill_label, False)
        labels['kills'] = kill_label

        b_chart = pygtk_chart.bar_chart.BarChart()
        vbox.pack_start(b_chart)

        for stat in ['units', 'bldgs']:
          area = pygtk_chart.bar_chart.Bar(stat, 0, stat)
          area.set_color(gtk.gdk.Color(*AI_STAT_COLORS[stat]))
          b_chart.add_bar(area)

        b_chart.grid.set_visible(False)
        b_chart.set_draw_labels(True)
        self.ai_drawables[str(a.team)] = (labels, b_chart)
        self.key_area.pack_start(vbox)

    def draw_grid(self, context):
        width = self.drawSize
        height = self.drawSize
        deltax = float(width)/self.drawSize
        deltay = float(height)/self.drawSize
        for i in xrange(self.world.mapSize):
            context.move_to(0, deltay*i)
            context.line_to(width, deltay*i)
            context.stroke()
            context.move_to(deltax*i, 0)
            context.line_to(deltax*i, height)
            context.stroke()

    def draw_map(self, world_data):


        width = self.drawSize
        height = self.drawSize

        surface = cairo.ImageSurface (cairo.FORMAT_ARGB32, width, height)
        cr = cairo.Context (surface)
        gdkcr = gtk.gdk.CairoContext (cr)
        worldmap.draw_map(gdkcr, width, height, world_data)

        self.guiTurn += 1

        # Draw the map
        cairo_context_final = self.map_area.window.cairo_create()
        pattern = cairo.SurfacePattern(surface)

        allocation = self.map_area.get_allocation()

        width = allocation.width
        height = allocation.height

        sx = width / float(self.drawSize)
        sy = height / float(self.drawSize)
        matrix = cairo.Matrix(xx=sx, yy=sy)
        cairo_context_final.transform(matrix)
        cairo_context_final.set_source(pattern)
        cairo_context_final.paint()



    def draw_map_and_ai_data(self):
        try:
          world_data, ai_data = json.loads(self.frame_queue.get(False))
        except Queue.Empty, e:
          return

        self.draw_map(world_data)
        self.update_ai_stats(ai_data, world_data["colors"])

    def update_ai_stats(self, ai_data, colors):
        for team in ai_data:
          team = str(team)
          labels, b_chart = self.ai_drawables[team]
          color = colors[team]
          for k in ['units', 'bldgs']:
            v = ai_data[team][k]
            bar = b_chart.get_area(k)
            if bar.get_value() != v:
              bar.set_value(int(v))

          for k in ['moving', 'shooting', 'idle', 'capturing']:
            v = ai_data[team][k]
            labels[k].set_text("%s: %s" % (k[0], v))
          v = ai_data[team][k]
          labels['kills'].set_text("kills: %s" % (ai_data[team]['kills']))

        self.key_area.show_all()



    def map_expose_event_cb(self, widget, event):
        self.draw_map_and_ai_data()

    def save_map_and_ai_data_to_queue(self):

        ai_data = {}
        for ai in self.world.AI:
          team = ai.team
          score = self.world.calcScore(team)
          ai_data[team] = { "units" : score["units"], "shooting" : 0, "capturing" : 0, "moving" : 0, "kills" : score["kills"], "idle" : 0, "bldgs" : score["buildings"]}
          for unit in self.world.units:
            status = self.world.unitstatus[unit]
            if self.world.units[unit].ai != ai:
              continue

            if status == world.MOVING:
              ai_data[team]["moving"] += 1
            elif status == world.SHOOTING:
              ai_data[team]["shooting"] += 1
            elif status == world.CAPTURING:
              ai_data[team]["capturing"] += 1
            else:
              ai_data[team]["idle"] += 1


        json_data = json.dumps((self.world.dumpToDict(), ai_data))
        self.frame_queue.put(json_data)


    def threaded_world_spinner(self):
        t = multiprocessing.Process(target=self.world_spinner)
        t.start()
        self.processes.append(t)

    def world_spinner(self):

        try:
            while not self.stopped:

              while self.frame_queue.full():
                if self.stopped:
                  sys.exit(0)
                  return
                time.sleep(0.05)

              self.world.spinAI()
              self.world.Turn()

              # Save world into a canvas that we put on a thread
              # safe queue
              self.save_map_and_ai_data_to_queue()
        except Exception, e:
            traceback.print_exc()
            if not settings.IGNORE_EXCEPTIONS:
              self.stopped = True
              end_game()
              sys.exit(1)

    def gui_spinner(self):
        log.info("GUI Showing Turn: %s", self.guiTurn)
        try:
          if self.stopped:
            sys.exit(0)

          self.draw_map_and_ai_data()
        except Exception, e:
          traceback.print_exc()
          if not settings.IGNORE_EXCEPTIONS:
            if self.map_area.window is None:
              self.stopped = True
              end_game()
              sys.exit(1) #window has closed
            self.stopped = False
        return True

m = None
def main(ais=[]):
    import sys
    import os

    global m
    m = MapGUI()
    for ai in ais:
      m.add_ai(ai)

    gobject.timeout_add(100, m.gui_spinner)
    m.threaded_world_spinner()
    gtk.main()

def end_game():
  for ai in m.world.AI:
    log.info("%s:%s", ai.__class__, ai.score)

def end_threads(*args, **kwargs):
  for proc in m.processes:
    proc.terminate()

if __name__ == "__main__":
  main()
