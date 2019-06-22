import datetime
import time
from collections import namedtuple
from base64 import urlsafe_b64encode, urlsafe_b64decode

from validr import validator, SchemaError, Invalid, Compiler, builtin_validators
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .helper import coerce_url
from .cursor import Cursor
from .detail import detail_validator
from . import unionid


@validator(accept=(str, object), output=(str, object))
def cursor_validator(compiler, keys=None, output_object=False, base64=False):
    """Cursor: k1:v1,k2:v2"""
    if keys:
        try:
            keys = set(keys.strip().replace(',', ' ').split())
        except (TypeError, ValueError):
            raise SchemaError('invalid cursor keys')

    def validate(value):
        try:
            if not isinstance(value, Cursor):
                if base64:
                    value = urlsafe_b64decode(value.encode('ascii')).decode('utf-8')
                value = Cursor.from_string(value, keys)
            else:
                value._check_missing_keys(keys)
        except (UnicodeEncodeError, UnicodeDecodeError, ValueError) as ex:
            raise Invalid(str(ex)) from None
        if output_object:
            return value
        value = str(value)
        if base64:
            value = urlsafe_b64encode(value.encode('utf-8')).decode()
        return value

    return validate


@validator(accept=str, output=str)
def url_validator(compiler, schemes='http https', default_schema=None):
    """
    Args:
        default_schema: 接受没有scheme的url并尝试修正
    """
    schemes = set(schemes.replace(',', ' ').split(' '))
    _django_validate_url = URLValidator(schemes=schemes)
    if default_schema and default_schema not in schemes:
        raise SchemaError('invalid default_schema {}'.format(default_schema))

    def validate(value):
        if default_schema:
            value = coerce_url(value, default_schema=default_schema)
        try:
            _django_validate_url(value)
        except ValidationError as ex:
            raise Invalid(','.join(ex.messages).rstrip('.'))
        return value

    return validate


@validator(accept=(str, object), output=(str, object))
def datetime_validator(compiler, format='%Y-%m-%dT%H:%M:%S.%fZ', output_object=False):
    def validate(value):
        try:
            if isinstance(value, list) and len(value) == 9:
                value = tuple(value)
            if isinstance(value, tuple):
                value = datetime.datetime.fromtimestamp(time.mktime(value), tz=timezone.utc)
            elif not isinstance(value, datetime.datetime):
                value = parse_datetime(value)
                if value is None:
                    raise ValueError('not well formatted at all')
            if not timezone.is_aware(value):
                value = timezone.make_aware(value, timezone=timezone.utc)
            if output_object:
                return value
            else:
                return value.strftime(format)
        except Exception as ex:
            raise Invalid('invalid datetime') from ex
    return validate


FeedUnionId = namedtuple('FeedUnionId', 'user_id, feed_id')
StoryUnionId = namedtuple('StoryUnionId', 'user_id, feed_id, offset')


def create_unionid_validator(tuple_class):
    @validator(accept=(str, object), output=(str, object))
    def unionid_validator(compiler, output_object=False):
        def validate(value):
            try:
                if isinstance(value, str):
                    value = unionid.decode(value)
                if output_object:
                    return tuple_class(*value)
                else:
                    return unionid.encode(*value)
            except (unionid.UnionIdError, TypeError, ValueError) as ex:
                raise Invalid('invalid unionid, {}'.format(str(ex))) from ex
        return validate
    return unionid_validator


def dict_validator(compiler, schema):
    schema = schema.copy()
    remove_empty = schema.params.pop('remove_empty', False)
    origin_validate = builtin_validators['dict'](compiler, schema)

    def validate(value):
        value = origin_validate(value)
        if value and remove_empty:
            value = {k: v for k, v in value.items() if v is not None and v != ''}
        return value

    return validate


VALIDATORS = {
    'cursor': cursor_validator,
    'url': url_validator,
    'datetime': datetime_validator,
    'feed_unionid': create_unionid_validator(FeedUnionId),
    'story_unionid': create_unionid_validator(StoryUnionId),
    'detail': detail_validator,
    'dict': dict_validator,
}


compiler = Compiler(validators=VALIDATORS)
