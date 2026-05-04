// interface/CutflowFlags.h
#ifndef CutflowFlags_h
#define CutflowFlags_h

#include "FWCore/Framework/interface/Event.h"
#include <map>
#include <string>
#include <memory>

// A simple named-flag container that a filter fills, then puts into the event.
// Usage:
//   CutflowFlags flags;
//   flags.set("MuonPt",  mu.pt() > 25.);
//   flags.set("MuonEta", std::abs(mu.eta()) < 2.4);
//   bool pass = flags.allPass();
//   flags.put(iEvent, "moduleAFlags");  // instanceLabel groups flags by module
//   return pass

class CutflowFlags {
public:
  void set(const std::string& name, bool value) {
    flags_[name] = value;
  }

  bool allPass() const {
    for (const auto& kv : flags_)
      if (!kv.second) return false;
    return true;
  }

  bool get(const std::string& name) const {
    auto it = flags_.find(name);
    return it != flags_.end() && it->second;
  }

  // Writes the map as individual bool products with instanceLabel prefix
  void put(edm::Event& iEvent, const std::string& instanceLabel) const {
        for (const auto& kv : flags_) {
            iEvent.put(std::make_unique<bool>(kv.second),
                    instanceLabel + kv.first);  // ✅ no underscore
        }
  }

  const std::map<std::string, bool>& flags() const { return flags_; }

private:
  std::map<std::string, bool> flags_;
};

#endif
