import pytest

from unittest import mock

from awx.api.versioning import reverse
from awx.main.models.ha import Instance

import redis

# Django
from django.test.utils import override_settings


INSTANCE_KWARGS = dict(hostname='example-host', cpu=6, memory=36000000000, cpu_capacity=6, mem_capacity=42)


@pytest.mark.django_db
def test_disabled_zeros_capacity(patch, admin_user):
    instance = Instance.objects.create(**INSTANCE_KWARGS)

    url = reverse('api:instance_detail', kwargs={'pk': instance.pk})

    r = patch(url=url, data={'enabled': False}, user=admin_user)
    assert r.data['capacity'] == 0

    instance.refresh_from_db()
    assert instance.capacity == 0


@pytest.mark.django_db
def test_enabled_sets_capacity(patch, admin_user):
    instance = Instance.objects.create(enabled=False, capacity=0, **INSTANCE_KWARGS)
    assert instance.capacity == 0

    url = reverse('api:instance_detail', kwargs={'pk': instance.pk})

    r = patch(url=url, data={'enabled': True}, user=admin_user)
    assert r.data['capacity'] > 0

    instance.refresh_from_db()
    assert instance.capacity > 0


@pytest.mark.django_db
def test_auditor_user_health_check(get, post, system_auditor):
    instance = Instance.objects.create(**INSTANCE_KWARGS)
    url = reverse('api:instance_health_check', kwargs={'pk': instance.pk})
    r = get(url=url, user=system_auditor, expect=200)
    assert r.data['cpu_capacity'] == instance.cpu_capacity
    post(url=url, user=system_auditor, expect=403)


@pytest.mark.django_db
@mock.patch.object(redis.client.Redis, 'ping', lambda self: True)
def test_health_check_usage(get, post, admin_user):
    instance = Instance.objects.create(**INSTANCE_KWARGS)
    url = reverse('api:instance_health_check', kwargs={'pk': instance.pk})
    r = get(url=url, user=admin_user, expect=200)
    assert r.data['cpu_capacity'] == instance.cpu_capacity
    assert r.data['last_health_check'] is None
    with override_settings(CLUSTER_HOST_ID=instance.hostname):  # force direct call of cluster_node_health_check
        r = post(url=url, user=admin_user, expect=200)
        assert r.data['last_health_check'] is not None
