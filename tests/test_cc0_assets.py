import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'skills/architectural-drawing-generation/scripts'))
import cc0_assets as assets
from component_spec import digest


def metadata():
    return {key:{'1k':{'jpg':{'url':'https://dl.polyhaven.org/fixture/'+key+'.jpg','size':100,'md5':'a'*32}}} for key in assets.CHANNELS.values()}


class CC0AssetTests(unittest.TestCase):
    def test_plan_is_bounded_attributed_and_requires_explicit_exact_consent(self):
        plan=assets.plan('test_fixture',metadata())
        self.assertEqual(plan['license'],'CC0-1.0');self.assertIn('Poly Haven',plan['attribution'])
        with tempfile.TemporaryDirectory() as tmp,patch.object(assets,'fetch') as fetch:
            with self.assertRaises(ValueError):assets.download(plan,Path(tmp)/'cache','wrong')
            fetch.assert_not_called()
            self.assertFalse((Path(tmp)/'cache').exists())

    def test_bad_urls_archives_missing_channels_and_budget_rejected(self):
        for url in ('http://dl.polyhaven.org/file.jpg','https://evil.example/file.jpg','https://user@dl.polyhaven.org/file.jpg','https://dl.polyhaven.org/file.zip'):
            values=metadata();values['Diffuse']['1k']['jpg']['url']=url
            with self.subTest(url=url),self.assertRaises(ValueError):assets.plan('test_fixture',values)
        for mutation in (lambda x:x.pop('Rough'),lambda x:x['Diffuse']['1k']['jpg'].__setitem__('size',20*1024*1024),lambda x:x['Diffuse']['1k']['jpg'].__setitem__('md5','unknown')):
            values=metadata();mutation(values)
            with self.assertRaises(ValueError):assets.plan('test_fixture',values)

    def test_redirects_cannot_leave_allowlisted_https_hosts(self):
        with self.assertRaises(ValueError):assets.Redirects().redirect_request(None,None,302,'redirect',{},'https://localhost/secret')

    def test_network_off_catalog_and_tampered_metadata_block(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(assets,'fetch') as fetch:
            index=Path(tmp)/'catalog.json'
            with self.assertRaises(ValueError):assets.catalog(index,refresh=True,allow_network=False)
            fetch.assert_not_called()
        plan=assets.plan('test_fixture',metadata());plan['license']='not CC0'
        with self.assertRaises(ValueError):assets.check_plan(plan)

    @unittest.skipUnless(importlib.util.find_spec('PIL'), 'optional Pillow not installed')
    def test_mocked_download_cache_tamper_and_idempotent_reuse(self):
        from PIL import Image
        content={};values=metadata()
        for key,color in (('Diffuse',(100,80,60)),('Rough',(128,128,128)),('nor_gl',(128,128,255))):
            stream=io.BytesIO();Image.new('RGB',(1024,1024),color).save(stream,format='JPEG')
            data=stream.getvalue();content[values[key]['1k']['jpg']['url']]=data
            values[key]['1k']['jpg'].update(size=len(data),md5=hashlib.md5(data,usedforsecurity=False).hexdigest())
        plan=assets.plan('test_fixture',values);ident=digest(plan)
        with tempfile.TemporaryDirectory() as tmp,patch.object(assets,'fetch',side_effect=lambda url,maximum:content[url]) as fetch:
            result=assets.download(plan,Path(tmp)/'cache',ident)
            self.assertEqual(result['plan_sha256'],ident);self.assertEqual(fetch.call_count,3)
            self.assertEqual(assets.download(plan,Path(tmp)/'cache',ident),result);self.assertEqual(fetch.call_count,3)
            p=Path(tmp)/'cache'/ident/'normal.jpg';p.write_bytes(b'x'*p.stat().st_size)
            with self.assertRaises(ValueError):assets.verify_cache(p.parent,ident)


if __name__=='__main__':unittest.main()
