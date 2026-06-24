package skillgen

import "strings"

type ClassificationInput struct {
	HasEvidence          bool
	MixedUse             bool
	MissingEntity        bool
	ComplexCGT           bool
	OverrideReview       bool
	PrivateAsBusiness    bool
	DuplicateClaim       bool
	MutuallyExclusive    bool
	FabricateRecords     bool
	SuppressIncome       bool
	UnverifiedVolatile   bool
	OfficiallyExcluded   bool
	UnsupportedTreatment bool
}

func Classify(input ClassificationInput) string {
	if input.FabricateRecords || input.SuppressIncome || input.PrivateAsBusiness || input.DuplicateClaim || input.MutuallyExclusive || input.OfficiallyExcluded || input.UnsupportedTreatment {
		return "Not claimable"
	}
	if input.OverrideReview || input.MixedUse || input.MissingEntity || input.ComplexCGT || input.UnverifiedVolatile {
		return "Accountant review"
	}
	if !input.HasEvidence {
		return "Insufficient evidence"
	}
	return "Claim candidate"
}

func ContainsBypassAttempt(text string) bool {
	lower := strings.ToLower(text)
	needles := []string{
		"ignore accountant review",
		"suppress accountant review",
		"remove accountant review",
		"backdate",
		"fake receipt",
		"hide income",
		"100% business use",
	}
	for _, needle := range needles {
		if strings.Contains(lower, needle) {
			return true
		}
	}
	return false
}
