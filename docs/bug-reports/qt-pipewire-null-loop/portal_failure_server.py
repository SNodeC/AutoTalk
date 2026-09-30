"""Private-bus ScreenCast responder for the native Qt failure probe; no desktop access."""
import os, socket, sys
import dbus, dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib
DBusGMainLoop(set_as_default=True)
bus=dbus.SessionBus();name=dbus.service.BusName('org.freedesktop.portal.Desktop',bus,do_not_queue=True)
class Request(dbus.service.Object):
 @dbus.service.signal('org.freedesktop.portal.Request',signature='ua{sv}')
 def Response(self,result,values):pass
class Portal(dbus.service.Object):
 starts=3 if sys.argv[1]=='remote-failure' else 0
 def reply(self,phase,values={}):
  path='/org/freedesktop/portal/desktop/request/test/'+phase
  request=Request(bus,path)
  result=0 if sys.argv[1]=='remote-failure' else (1 if self.starts%5==1 else 0) if sys.argv[1]=='cycle' else int(sys.argv[1])
  def respond():request.Response(result if phase=='start' else 0,values);request.remove_from_connection();return False
  GLib.timeout_add(20,respond)
  return dbus.ObjectPath(path)
 @dbus.service.method('org.freedesktop.DBus.Properties',in_signature='ss',out_signature='v')
 def Get(self,interface,property):return dbus.UInt32(4)
 @dbus.service.method('org.freedesktop.portal.ScreenCast',in_signature='a{sv}',out_signature='o')
 def CreateSession(self,options):return self.reply('create',{'session_handle':dbus.String('/org/freedesktop/portal/desktop/session/test')})
 @dbus.service.method('org.freedesktop.portal.ScreenCast',in_signature='oa{sv}',out_signature='o')
 def SelectSources(self,session,options):return self.reply('select')
 @dbus.service.method('org.freedesktop.portal.ScreenCast',in_signature='osa{sv}',out_signature='o')
 def Start(self,session,parent,options):
  self.starts+=1
  node=os.environ.get('QT_TEST_PIPEWIRE_NODE')
  if node and sys.argv[1]=='cycle' and self.starts%5==3:node=str(2**32-2)
  values={'streams':dbus.Array([dbus.Struct((dbus.UInt32(int(node)),dbus.Dictionary({'size':dbus.Struct((dbus.Int32(640),dbus.Int32(480))), 'source_type':dbus.UInt32(1)},signature='sv')),signature='ua{sv}')],signature='(ua{sv})')} if node else {}
  return self.reply('start',values)
 @dbus.service.method('org.freedesktop.portal.ScreenCast',in_signature='oa{sv}',out_signature='h')
 def OpenPipeWireRemote(self,session,options):
  assert 'QT_TEST_PIPEWIRE_NODE' in os.environ
  if sys.argv[1]=='remote-failure' or sys.argv[1]=='cycle' and self.starts%5==4:
   raise dbus.DBusException('Synthetic remote failure',name='org.freedesktop.portal.Error.Failed')
  with socket.socket(socket.AF_UNIX) as remote:
   remote.connect(os.environ['XDG_RUNTIME_DIR']+'/pipewire-0')
   return dbus.types.UnixFd(remote.fileno())
p=Portal(bus,'/org/freedesktop/portal/desktop');print('ready',flush=True);GLib.MainLoop().run()
