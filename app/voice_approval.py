"""One fresh read-back, one decision; never approve an old or changed proposal."""
import copy
import re
import time


class Approval:
 def __init__(self):self.offer=None
 def clear(self):self.offer=None
 def arm(self,items):
  self.offer={'items':copy.deepcopy(items),'at':time.monotonic()} if items else None
 def consume(self,text,pending):
  text=re.sub(r'^(?:hey )?jinx[, ]+','',str(text).strip().lower()).strip(' .!?')
  yes=text in ('yes','yes please','yes, please','yes do it','yes, do it','go ahead','confirm','yes install it','yes, install it','ja','ja bitte','ja, bitte','ja mach das','bestätigen')
  no=text in ('no','no thanks','no, thanks','cancel','cancel it',"don't do it",'do not do it','nein','nein danke','abbrechen','nicht machen')
  offer=self.offer;self.clear()
  if not offer:return None
  if offer['items'][0].get('kind')=='calendar_delete' and text in ('yes delete it','yes, delete it','yes remove it','yes, remove it','delete it','remove it'):
   yes=True
  if not (yes or no):return None
  items=offer['items'];current=next((p for p in pending if p['id']==items[0]['id']),None)
  if time.monotonic()-offer['at']>120 or current!=items[0]:
   return {'decision':'stale','items':[]}
  return {'decision':'yes' if yes else 'no','item':current,'items':items[1:]}
