import { logger } from "./log.js";


function checkScene(scene) {
    // 发送对scene的检查请求 : label合法性
    const req = new Request(`/api/projects/${scene}/check_label`);
    let init = {
        method: 'GET',
        //body: JSON.stringify({"points": data})
    };
    // we defined the xhr

    return fetch(req, init)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            } else {
                return response.json();
            }
        })
        .then(ret => {
            logger.setErrorsContent(ret);
        })
        .catch(reject => {
            console.log("error check scene!");
        });
}

export { checkScene };
