"""Base classes."""
import logging
import dataclasses
import json
from typing import List, Union
from pathlib import Path

import uuid
import shutil

import zipfile, io, os

import yaml
from requests import Response

from supersetapiclient.exceptions import NotFound

from .logger import LogConfig

logger = LogConfig("superset_client").logger


def json_field():
    return dataclasses.field(default=None, repr=False)


def default_string():
    return dataclasses.field(default="", repr=False)


class Object:
    _parent = None
    EXPORTABLE = False
    JSON_FIELDS = []

    @classmethod
    def fields(cls):
        """Get field names."""
        return dataclasses.fields(cls)

    @classmethod
    def field_names(cls):
        """Get field names."""
        return set(
            f.name
            for f in dataclasses.fields(cls)
        )

    @classmethod
    def from_json(cls, json: dict):
        """Create Object from json

        Args:
            json (dict): a dictionary

        Returns:
            Object: return the related object
        """
        field_names = cls.field_names()
        return cls(**{k: v for k, v in json.items() if k in field_names})

    def __post_init__(self):
        for f in self.JSON_FIELDS:
            setattr(self, f, json.loads(getattr(self, f) or "{}"))

    @property
    def base_url(self) -> str:
        return self._parent.client.join_urls(
            self._parent.base_url,
            # str(self.id)
        )

    @property
    def import_url(self) -> str:
        return self._parent.client.join_urls(
            self._parent.base_url,
            "import/",
            # str(self.id),
        )

    @property
    def export_url(self) -> str:
        """Export url for a single object."""
        # Note that params should be passed on run
        # to bind to a specific object
        return self._parent.client.join_urls(
            self.base_url,
            "export/",
            # str(self.id),
        )

    @property
    def test_connection_url(self) -> str:
        return self._parent.client.join_urls(
            self._parent.base_url,
            str(self.id)
        )

    def export(self, path: Union[Path, str], filename:str=None) -> None:
        """Export object to path"""
        if not self.EXPORTABLE:
            raise NotImplementedError(
                "Export is not defined for this object."
            )

        # Get export response
        if not filename:
            filename = str(uuid.uuid4())

        client = self._parent.client
        response = client.get(self.export_url, params={
            "q": f"!({self.id})"  # Object must have an id field to be exported
        })
        response.raise_for_status()

        data = response.content
        with open(path, 'wb') as f:
            f.write(data)


    def fetch(self) -> None:
        """Fetch and set object information from remote
        (updates if changes made remotely)"""

        field_names = self.field_names()

        client = self._parent.client
        response = client.get(self.base_url)

        o = response.json()
        o = [x for x in o.get("result") if x['id']==self.id][0]

        for k, v in o.items():
            if k in field_names:
                setattr(self, k, v)

    def save(self) -> None:
        """Save object information."""
        o = {}
        for c in self._parent.edit_columns:
            if hasattr(self, c):
                value = getattr(self, c)

                if c in self.JSON_FIELDS:
                    value = json.dumps(value)
                o[c] = value

        response = self._parent.client.put(self.base_url + str(self.id), json=o)

        if response.status_code in [400, 422]:
            logger.error(response.text)

        response.raise_for_status()


class ObjectFactories:
    endpoint = ""
    base_object = None

    _INFO_QUERY = {
        "keys": [
            "add_columns",
            "edit_columns"
        ]
    }

    def __init__(self, client):
        """Create a new Dashboards endpoint.

        Args:
            client (client): superset client
        """
        self.client = client

        # Get infos
        response = client.get(
            client.join_urls(
                self.base_url,
                "_info",
            ),
            params={
                "q": json.dumps(self._INFO_QUERY)
            })

        if response.status_code != 200:
            logger.error(f"Unable to build object factory for {self.endpoint}")
            response.raise_for_status()

        infos = response.json()

        # Due to the design of the superset API,
        # get /chart/_info only returns 'slice_name'
        # for chart adds to work,
        # we require the additional attributes:
        #   'datasource_id',
        #   'datasource_type'

        if self.__class__.__name__ == 'Charts':

            self.edit_columns = [
                'datasource_id',
                'datasource_type',
                'slice_name',
                'params',
                'viz_type',
                'description'
            ]

            self.add_columns = [
                'datasource_id',
                'datasource_type',
                'slice_name',
                'params',
                'viz_type',
                'description'
            ]

        else:

            self.edit_columns = [
                e.get("name")
                for e in infos.get("edit_columns", [])
            ]

            self.add_columns = [
                e.get("name")
                for e in infos.get("add_columns", [])
            ]

    @property
    def base_url(self):
        """Base url for these objects."""
        return self.client.join_urls(
            self.client.base_url,
            self.endpoint,
        )

    @property
    def import_url(self):
        """Base url for these objects."""
        return self.client.join_urls(
            self.client.base_url,
            self.endpoint,
            "import/"
        )

    @property
    def export_url(self):
        """Base url for these objects."""
        return self.client.join_urls(
            self.client.base_url,
            self.endpoint,
            "export/"
        )

    @property
    def test_connection_url(self):
        """Base url for these objects."""
        return self.client.join_urls(
            self.client.base_url,
            self.endpoint,
            "test_connection"
        )

    @staticmethod
    def _handle_reponse_status(response: Response) -> None:
        """Handle response status."""
        if response.status_code not in (200, 201):
            logger.error(
                f"Unable to proceed, API return {response.status_code}"
            )
            logger.error(f"Full API response is {response.text}")

        # Finally raising for status
        response.raise_for_status()

    def get(self, id: int):
        """Get an object by id."""
        url = self.base_url + str(id)
        response = self.client.get(
            url
        )
        response.raise_for_status()
        response = response.json()

        object_json = response.get("result")
        object_json["id"] = id
        object = self.base_object.from_json(object_json)
        object._parent = self

        return object

    def find(self, page_size: int = 100, page: int = 0, **kwargs):
        """Find and get objects from api."""
        url = self.base_url

        # Get response
        query = {
                "page_size": page_size,
                "page": page,
                "filters": [
                    {
                        "col": k,
                        "opr": "eq",
                        "value": v
                    } for k, v in kwargs.items()
                ]
        }

        params = {
            "q": json.dumps(query)
        }

        response = self.client.get(
            url,
            params=params
        )
        response.raise_for_status()
        response = response.json()

        objects = []
        for r in response.get("result"):
            o = self.base_object.from_json(r)
            o._parent = self
            objects.append(o)

        return objects

    def count(self):
        """Count objects."""

        # To do : add kwargs parameters for more flexibility
        response = self.client.get(self.base_url)

        if response.status_code not in (200, 201):
            logger.error(response.text)
        response.raise_for_status()

        json = response.json()
        return(json['count'])

    def find_one(self, **kwargs):
        """Find only object or raise an Exception."""
        objects = self.find(**kwargs)
        if len(objects) == 0:
            raise NotFound(f"No {self.base_object.__name__} has been found.")
        return objects[0]

    def add(self, obj) -> int:
        """Create an object on remote."""

        o = {}
        for c in self.add_columns:
            if hasattr(obj, c):
                value = getattr(obj, c)

                if c in obj.JSON_FIELDS:
                    value = json.dumps(value)
                o[c] = value

        response = self.client.post(self.base_url, json=o)
        response.raise_for_status()
        return response.json().get("id")

    def export(self, ids: List[int], path: Union[Path, str]) -> None:
        """Export object into an importable file"""
        client = self.client
        url = self.export_url
        ids_array = ','.join([str(i) for i in ids])
        response = client.get(
            url,
            params={
                # "q": "!(" + ",".join([str(x) for x in ids_array]) + ")"
                "q": "!(" + ids_array + ")"
            })

        if response.status_code not in (200, 201):
            logger.error(response.text)
        response.raise_for_status()

        content_type = response.headers["content-type"].strip()

        if content_type.startswith("application/text"):
            data = response.text
            data = yaml.load(data, Loader=yaml.FullLoader)
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False)
        else:
            data = response.content
            with open(path, 'wb') as f:
                f.write(data)

        return response.status_code

    def delete(self, id) -> int:
        """Delete a object on remote."""
        response = self.client.delete(self.base_url + str(id))

        if response.status_code not in (200, 201):
            logger.error(response.text)
        response.raise_for_status()

        if response.json().get('message') == 'OK':
            return True
        else:
            return False

    def import_file(self, file_path) -> int:
        """Import a file on remote."""
        url = self.import_url

        file = {'formData': (file_path, open(
            file_path, 'rb'), 'application/json')}

        response = self.client.post(url, files=file)
        response.raise_for_status()

        # If import is successful,
        # the following is returned: {'message': 'OK'}
        return response.json()

    def test_connection(self, obj):
        """Import a file on remote."""
        url = self.test_connection_url
        connection_columns = ['database_name', 'sqlalchemy_uri']
        o = {}
        for c in connection_columns:
            if hasattr(obj, c):
                value = getattr(obj, c)
                o[c] = value

        response = self.client.post(url, json=o)
        if response.json().get('message') == 'OK':
            return True
        else:
            return False
