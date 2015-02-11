from django.contrib import messages
from django.shortcuts import render, redirect
from django.db import transaction
from django.db.models import Count

from jsonview.decorators import json_view

from airmozilla.main.models import Event, Template
from airmozilla.manage import forms

from .decorators import (
    staff_required,
    permission_required,
    cancel_redirect
)
from .utils import get_var_templates


@staff_required
@permission_required('main.change_template')
@json_view
def template_env_autofill(request):
    """JSON response containing undefined variables in the requested template.
       Provides template for filling in environment."""
    template_id = request.GET['template']
    template = Template.objects.get(id=template_id)
    var_templates = get_var_templates(template)

    return {'variables': '\n'.join(var_templates)}


@staff_required
@permission_required('main.change_template')
def templates(request):
    context = {}
    context['templates'] = Template.objects.all()

    counts = {}

    events = Event.objects.all()
    for each in events.values('template').annotate(Count('template')):
        counts[each['template']] = each['template__count']

    counts_removed = {}
    events = events.filter(status=Event.STATUS_REMOVED)
    for each in events.values('template').annotate(Count('template')):
        counts_removed[each['template']] = each['template__count']

    # def count_events_with_template(template):
    #     return Event.objects.filter(template=template).count()
    #
    # def count_removed_events_with_template(template):
    #     return Event.objects.filter(
    #         template=template,
    #         status=Event.STATUS_REMOVED
    #     ).count()

    context['counts'] = counts
    context['counts_removed'] = counts_removed
    return render(request, 'manage/templates.html', context)


@staff_required
@permission_required('main.change_template')
@cancel_redirect('manage:templates')
@transaction.commit_on_success
def template_edit(request, id):
    template = Template.objects.get(id=id)
    if request.method == 'POST':
        form = forms.TemplateEditForm(request.POST, instance=template)
        if form.is_valid():
            template = form.save()
            if template.default_popcorn_template:
                others = (
                    Template.objects.filter(default_popcorn_template=True)
                    .exclude(pk=template.pk)
                )
                for other_template in others:
                    other_template.default_popcorn_template = False
                    other_template.save()
            if template.default_archive_template:
                others = (
                    Template.objects.filter(default_archive_template=True)
                    .exclude(pk=template.pk)
                )
                for other_template in others:
                    other_template.default_archive_template = False
                    other_template.save()

            messages.info(request, 'Template "%s" saved.' % template.name)
            return redirect('manage:templates')
    else:
        form = forms.TemplateEditForm(instance=template)

    events = Event.objects.filter(template=template).order_by('modified')
    context = {
        'form': form,
        'template': template,
        'events_count': events.count(),
        'events': events[:100],  # cap it so it doesn't get too big
    }
    return render(request, 'manage/template_edit.html', context)


@staff_required
@permission_required('main.add_template')
@cancel_redirect('manage:templates')
@transaction.commit_on_success
def template_new(request):
    if request.method == 'POST':
        form = forms.TemplateEditForm(request.POST, instance=Template())
        if form.is_valid():
            form.save()
            messages.success(request, 'Template created.')
            return redirect('manage:templates')
    else:
        form = forms.TemplateEditForm()
    return render(request, 'manage/template_new.html', {'form': form})


@staff_required
@permission_required('main.delete_template')
@transaction.commit_on_success
def template_remove(request, id):
    if request.method == 'POST':
        template = Template.objects.get(id=id)
        template.delete()
        messages.info(request, 'Template "%s" removed.' % template.name)
    return redirect('manage:templates')
