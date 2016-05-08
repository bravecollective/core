def get_membership(info):
    print info
    from brave.core.character.model import EVEAlliance, EVECorporation, EVECharacter
    # don't remove any of model imports even if they seem unused
    # they have to be imported because of how mongoengine works
    # also, this import has to be inside the method, because
    # otherwise paster can't find the module

    # This is a stupid edge-case to cover inconsistency between API calls.
    allianceID = info['alliance']['id']
    allianceName = info['alliance']['name'] if info['alliance']['name'] else None
    corporationName = info['corp']['name']


    alliance, created = EVEAlliance.objects.get_or_create(
            identifier=allianceID,
            defaults=dict(name=allianceName)
        ) if allianceID else (None, False)

    if alliance and not created and alliance.name != allianceName:
        alliance.name = allianceName
        alliance = alliance.save()

    corporation, created = EVECorporation.objects.get_or_create(
            identifier=info['corp']['id'],
            defaults=dict(name=corporationName, alliance=alliance)
        )

    if corporation.name != corporationName:
        corporation.name = corporationName

    corporation.alliance = alliance

    if corporation._changed_fields:
        corporation = corporation.save()

    return corporation, alliance