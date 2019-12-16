function show_node_info(id){
    // Find correct node from nodes
    data = graph.nodes.find((x) => x.id == id);

    $("svg.graph .nodes .node").removeClass("active");
    const dom_node = $("svg.graph .nodes .node")[data.index];
    $(dom_node).addClass("active")

    color = node_color(data)
    document.getElementById("modalheader").style.backgroundColor = color;

    $("#candidateImage").attr("src", (data.image) ? data.image : default_image)
    $("#candidateName").text("Name: " + data.name)
    $("#candidateNumber").text("Candidate number: " + data.number)
    $("#candidateParty").text("Party: " + data.party)
    $("#candidateConstituency").text("Constituency: " + data.constituency)
    $("#candidateTalkinpoint").text(data.talkinpoint)

    const rel_el = $("#candidateRelated");
    // Remove old html nodes.
    $("> .candidate", rel_el).remove()

    // Read template
    const template = $("#candidateRelatedTemplate").html().trim();

    // Find related candidates, and show nearest first.
    graph.links.filter((x) => x.target.id == id || x.source.id == id).sort((a, b) => b.distance - a.distance ).forEach(function(link) {
        let node;
        let topic;
        // It's not known if current node is source or target, so check is needed.
        if (link.target.id == id) {
            node = link.source;
            topic = link.source_term;
        } else {
            node = link.target;
            topic = link.target_term;
        }
        // Create new element from template, and populate values.
        let el = $(template)
            .attr("title", node.number+": "+node.name+"\n"+node.party+"\n"+node.constituency)
            .click(() => show_node_info(node.id))
            // .hover(function() {
            //     const _n = document.querySelectorAll(".nodes .node")[node.index];
            //     $(_n).addClass("hover");
            //     redraw();
            // }, function() {
            //     const _n = document.querySelectorAll(".nodes .node")[node.index];
            //     $(_n).removeClass("hover");
            //     redraw();
            // });
        $("img.node", el)
            .attr("src", node.image ? node.image : default_image)
            .attr("style", "border-color:"+node_color(node))
        $(".topic", el).text(topic);
        $(".name", el).text(node.name);

        // Append into a node tree.
        rel_el.append(el);

    })

    $("#candidateInformationModal").modal('show')
    $('.modal-backdrop').removeClass("modal-backdrop");
    $(".modal-dialog").draggable({
        "handle":".modal-header",
        "containment":"window"
    });

}

function ui_init_filters(nodes) {
    // Kerää puolueet ja vaalipiirit solmuista
    const parties = []
    const constituencies = []

    nodes.forEach(node => {

        var party = node.party
        var constituency = node.constituency

        if (parties.indexOf(party) == -1) {
            parties.push(party)
        }
        if(constituencies.indexOf(constituency) == -1){
            constituencies.push(constituency)
        }
    });

    parties.forEach(function(party) {

        let list_item = $("<li><label>");
        list_item.find("label").text(party);

        let checkbox = $("<input type =\"checkbox\" checked>")
        checkbox.attr("name", "party");
        checkbox.attr("value", party);

        checkbox.on("click", function() {checkboxClick(checkbox)})

        /*checkbox.on("click", function() {

            const filter_rules = {
                party: [],
                constituency: []
            }

            $("#filter-party input:not(:checked").each(function(){
                filter_rules['party'].push($(this).val());
            })

            // Kutsu filtteröintiä.
            graph_filter(filter_rules)
        });*/

        list_item.find("label").prepend(checkbox)
        $("#filter-party").append(list_item);
    });

    constituencies.forEach(function(constituency) {

        let list_item = $("<li><label>");
        list_item.find("label").text(constituency);
        let checkbox = $("<input type =\"checkbox\" checked>")
        checkbox.attr("name", "constituency");
        checkbox.attr("value", constituency);

        checkbox.on("click", function() {checkboxClick(checkbox)})

        /*checkbox.on("click", function() {


            const filter_rules = {
                party: [],
                constituency: []
            }

            $("#filter-constituency input:not(:checked").each(function(){
                filter_rules['constituency'].push($(this).val());
            })

            graph_filter(filter_rules);
        })*/
        list_item.find("label").prepend(checkbox)
        $("#filter-constituency").append(list_item);
    });

    function checkboxClick(checkbox){

        const filter_rules = {
            party: [],
            constituency: []
        }

         $("#filter-party input:not(:checked").each(function(){
             filter_rules['party'].push($(this).val());
         })
         $("#filter-constituency input:not(:checked").each(function(){
             filter_rules['constituency'].push($(this).val());
         })

        graph_filter(filter_rules);
    }
}
