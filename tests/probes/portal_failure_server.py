"""Private-bus ScreenCast responder for the native Qt failure probe; no desktop access."""
import sys
import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus();name=dbus.service.BusName('org.freedesktop.portal.Desktop',bus)
class Request(dbus.service.Object):
 @dbus.service.signal('org.freedesktop.portal.Request',signature='ua{sv}')
 def Response(self,result,values):pass
class Portal(dbus.service.Object):
 def reply(self,phase,values={}):
  path='/org/freedesktop/portal/desktop/request/test/'+phase
  request=Request(bus,path)
  def respond():request.Response(int(sys.argv[1]) if phase=='start' else 0,values);request.remove_from_connection();return False
  GLib.timeout_add(20,respond)
  return dbus.ObjectPath(path)
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
 def Get(self,interface,property):return dbus.UInt32(4)
 @dbus.service.method('org.freedesktop.portal.ScreenCast',in_signature='a{sv}',out_signature='o')
 def CreateSession(self,options):return self.reply('create',{'session_handle':dbus.String('/org/freedesktop/portal/desktop/session/test')})
 @dbus.service.method('org.freedesktop.portal.ScreenCast',in_signature='oa{sv}',out_signature='o')
 def SelectSources(self,session,options):return self.reply('select')
 @dbus.service.method('org.freedesktop.portal.ScreenCast',in_signature='osa{sv}',out_signature='o')
 def Start(self,session,parent,options):return self.reply('start')
p=Portal(bus,'/org/freedesktop/portal/desktop');print('ready',flush=True);GLib.MainLoop().run()
