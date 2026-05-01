import FWCore.ParameterSet.Config as cms


_RUN2_BAD_DET_ECAL = [
    872439604, 872422825, 872420274, 872423218,
    872423215, 872416066, 872435036, 872439336,
    872420273, 872436907, 872420147, 872439731,
    872436657, 872420397, 872439732, 872439339,
    872439603, 872422436, 872439861, 872437051,
    872437052, 872420649, 872422436, 872421950,
    872437185, 872422564, 872421566, 872421695,
    872421955, 872421567, 872437184, 872421951,
    872421694, 872437056, 872437057, 872437313,
]

_RUN3_2022_2023_BAD_DET_ECAL = [838871812]


def _normalize_year(year_or_era):
    value = str(year_or_era).strip()
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) < 4:
        return ""
    return digits[:4]


def makeEcalBadCalibFilter(year_or_era, tagging_mode = False):
    year = _normalize_year(year_or_era)

    if year in ("2016", "2017", "2018"):
        return cms.EDFilter(
            "EcalBadCalibFilter",
            EcalRecHitSource = cms.InputTag("reducedEgamma", "reducedEERecHits"),
            ecalMinEt = cms.double(50.0),
            baddetEcal = cms.vuint32(*_RUN2_BAD_DET_ECAL),
            taggingMode = cms.bool(tagging_mode),
            debug = cms.bool(False),
        )

    if year in ("2022", "2023"):
        return cms.EDFilter(
            "EcalBadCalibFilter",
            EcalRecHitSource = cms.InputTag("reducedEgamma", "reducedEBRecHits"),
            ecalMinEt = cms.double(50.0),
            baddetEcal = cms.vuint32(*_RUN3_2022_2023_BAD_DET_ECAL),
            taggingMode = cms.bool(tagging_mode),
            debug = cms.bool(False),
        )

    return None


def addEcalBadCalibFilter(process,
                          year_or_era,
                          module_name = "ecalBadCalibReducedMINIAODFilter",
                          tagging_mode = False):
    module = makeEcalBadCalibFilter(year_or_era, tagging_mode = tagging_mode)
    if module is None:
        return None

    setattr(process, module_name, module)
    return getattr(process, module_name)
